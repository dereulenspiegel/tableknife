#!/usr/bin/python

# Based on software by:
# Author : n0fate
# E-Mail rapfer@gmail.com, n0fate@live.com
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA
#
# Using structures defined in Wikipedia('http://en.wikipedia.org/wiki/GUID_Partition_Table')
#
# I modified the source code to not only print the GPT but modify it so we can insert 
# binary payloads


import getopt
import sys
import struct
import hashlib

import uuid

import zlib

import argparse

LBA_SIZE = 512

PRIMARY_GPT_LBA = 1

OFFSET_CRC32_OF_HEADER = 16
GPT_HEADER_FORMAT = '<8sIIIIQQQQ16sQIII420x'
GUID_PARTITION_ENTRY_FORMAT = '<16s16sQQQ72s'


## gpt parser code start

def get_lba(fhandle, entry_number, count):
    fhandle.seek(LBA_SIZE*entry_number)
    fbuf = fhandle.read(LBA_SIZE*count)
    
    return fbuf

def write_lba(fhandle, offset, fbuf):
    fhandle.seek(LBA_SIZE*offset)
    fhandle.write(fbuf)

def unsigned32(n):
  return n & 0xFFFFFFFFL

def get_gpt_header(fhandle, fbuf, lba):
    fbuf = get_lba(fhandle, lba, 1)
    
    gpt_header = struct.unpack(GPT_HEADER_FORMAT, fbuf)
    
    crc32_header_value = calc_header_crc32(fbuf, gpt_header[2])
    
    return gpt_header, crc32_header_value, fbuf

def make_nop(byte):
    nop_code = 0x00
    pk_nop_code = struct.pack('=B', nop_code)
    nop = pk_nop_code*byte
    return nop

def calc_header_crc32(fbuf, header_size):
    
    nop = make_nop(4)
    
    clean_header = fbuf[:OFFSET_CRC32_OF_HEADER] + nop + fbuf[OFFSET_CRC32_OF_HEADER+4:header_size]
    
    crc32_header_value = unsigned32(zlib.crc32(clean_header))
    return crc32_header_value

# get partition entry
def get_part_entry(fbuf, offset, size):
    return struct.unpack(GUID_PARTITION_ENTRY_FORMAT, fbuf[offset:offset+size])

def get_part_table_area(f, gpt_header):
    part_entry_start_lba = gpt_header[10]
    first_use_lba_for_partitions = gpt_header[7]
    fbuf = get_lba(f, part_entry_start_lba, first_use_lba_for_partitions - part_entry_start_lba)
    
    return fbuf

def write_part_table_area(f, gpt_header, fbuf):
    partition_table_offset = gpt_header[10]
    f.seek(LBA_SIZE * partition_table_offset)
    f.write(fbuf)

# I don't know how to use struct.pack with a tuple. Have to read about it
def pack_gpt_header(gpt_header):
    gbuf = struct.pack(GPT_HEADER_FORMAT,gpt_header[0],gpt_header[1],gpt_header[2],gpt_header[3],gpt_header[4],gpt_header[5],gpt_header[6],gpt_header[7],gpt_header[8],gpt_header[9],gpt_header[10],gpt_header[11],gpt_header[12],gpt_header[13])
    return gbuf

def setPartitionTableStart(gpt_header, lbaOffset, ptable_checksum, backup):
    crc32_header = gpt_header[3]
    first_use_lba_for_partitions = gpt_header[7]
    part_entry_start_lba = gpt_header[10]

    gpt_header = list(gpt_header)
    if not backup:
        gpt_header[10] = part_entry_start_lba + lbaOffset

    gpt_header[13] = ptable_checksum
    gpt_header[7] = first_use_lba_for_partitions + lbaOffset
    gbuf = pack_gpt_header(gpt_header)
    gpt_header[3] = calc_header_crc32(gbuf, gpt_header[2])

    return tuple(gpt_header)

def readPayload(path,offset):
    payloadFile = open(path,'rb')
    payloadFile.seek(offset)
    payloadBuf = payloadFile.read()
    return payloadBuf

def pack_partition_table_entry(part_entry):
    return struct.pack(GUID_PARTITION_ENTRY_FORMAT,part_entry[0],part_entry[1],part_entry[2],part_entry[3],part_entry[4],part_entry[5])

def moveStartOfPartition(partition_table, partitionNumber, gpt_header, offset):
    num_of_part_entry = gpt_header[11]
    size_of_part_entry = gpt_header[12]
    crc32_of_partition_array = gpt_header[13]

    part_entry = get_part_entry(partition_table, size_of_part_entry * (partitionNumber-1), size_of_part_entry)
    start_lba = part_entry[2]
    part_entry = list(part_entry)
    part_entry[2] = start_lba + offset
    part_entry = tuple(part_entry)

    binary_entry = pack_partition_table_entry(part_entry)
    part_table_start = partition_table[0:size_of_part_entry * (partitionNumber - 1) ]
    part_table_end = partition_table[(size_of_part_entry * partitionNumber) : len(partition_table)]
    new_partition_table = part_table_start + binary_entry + part_table_end

    new_checksum = unsigned32(zlib.crc32(new_partition_table))

    return new_partition_table, new_checksum

def findFirstPartitionOnDisk(partition_table, gpt_header):
    partitionCount = gpt_header[11]
    size_of_part_entry = gpt_header[12]

    numberOfFirstPartition = -1

    lowestLBA = sys.maxint

    for entryNum in range(0,partitionCount):
        partEntry = get_part_entry(partition_table, size_of_part_entry*entryNum, size_of_part_entry)

        if partEntry[2] == 0 or partEntry[3] == 0:
            continue
        else if lowestLBA < partEntry[2]:
            lowestLBA = partEntry[2]
            numberOfFirstPartition = entryNum

    return numberOfFirstPartition

def movePartitionTableEntries(f, args):
    payload = readPayload(args.payload[0],args.skip)

    fbuf = ''
    offset = len(payload) / LBA_SIZE + 1

    gpt_header, crc32_header_value, gpt_buf = get_gpt_header(f, fbuf, PRIMARY_GPT_LBA)
    pbuf = get_part_table_area(f, gpt_header)
    firstPartition = findFirstPartitionOnDisk(pbuf,gpt_header)
    partition_table, ptable_checksum = moveStartOfPartition(pbuf, firstPartition, gpt_header, offset)
    gpt_header = setPartitionTableStart(gpt_header, offset, ptable_checksum, False)

    gbuf = pack_gpt_header(gpt_header)
    write_lba(f, PRIMARY_GPT_LBA, gbuf)

    write_part_table_area(f,gpt_header,partition_table)

    # Write Payload to LBA 2
    write_lba(f, 2, payload)

    # Read and modify secondary Header
    secondaryHeaderOffset = gpt_header[6]
    gpt_header, crc32_header_value, gpt_buf = get_gpt_header(f, fbuf, secondaryHeaderOffset)
    gpt_header = setPartitionTableStart(gpt_header, offset, ptable_checksum, True)
    gbuf = pack_gpt_header(gpt_header)
    write_lba(f, secondaryHeaderOffset, gbuf)
    write_part_table_area(f,gpt_header,partition_table)

def doIt():

    args = parseArguments()
    
    try:
        f = open(args.disk[0], 'r+b')
    except IOError:
        print 'WARNING!! Can not open disk image.'
        sys.exit()

    print 'Modifying GPT of %s and adding the payload %s while skipping %d bytes of the payload'%(args.disk[0],args.payload[0],args.skip)

    movePartitionTableEntries(f, args)

    f.close()

def parseArguments():
    parser = argparse.ArgumentParser(description='Insert a bootable payload between GTP header and table')
    parser.add_argument('--disk',nargs=1,required=True,help='Specify the disk(image), on which the GPT should modified',dest='disk')
    parser.add_argument('--payload',nargs=1,required=True,help='Specifiy the payload which should be put between GPT header and table',dest='payload')
    parser.add_argument('--skip',default='0',type=int,help='Skip this many bytes blocks from the input file',dest='skip')
    parser.add_argument('--part-num',type=int,required=False,help='Number of the first partition after the table, for ChromiumOS this is 11',dest='partNum')

    args = parser.parse_args()
    return args

    
if __name__ == "__main__":
    doIt()
