import getopt
import sys
import struct
import hashlib
import stat

import uuid

import zlib

import argparse

import os
import subprocess

LBA_SIZE = 512

PRIMARY_GPT_LBA = 1

OFFSET_CRC32_OF_HEADER = 16
GPT_HEADER_FORMAT = '<8sIIIIQQQQ16sQIII420x'
GUID_PARTITION_ENTRY_FORMAT = '<16s16sQQQ72s'

def get_lba(fhandle, entry_number, count):
    fhandle.seek(LBA_SIZE*entry_number)
    fbuf = fhandle.read(LBA_SIZE*count)
    
    return fbuf

def write_lba(fhandle, offset, fbuf):
    fhandle.seek(LBA_SIZE*offset)
    fhandle.write(fbuf)

def update_gpt(fhandle, gpt_header):
	gbuf = pack_gpt_header(gpt_header)
	crc32_checksum = calc_header_crc32(gbuf, gpt_header[2])
	gptBlock = gpt_header[5]
	gpt_header = list(gpt_header)
	gpt_header[3] = crc32_checksum
	gpt_header = tuple(gpt_header)
	gbuf = pack_gpt_header(gpt_header)
	print 'Writing GPT header to block %d'%gptBlock
	write_lba(fhandle, gptBlock, gbuf)

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
    part_entry_count = gpt_header[11]
    part_entry_size_in_bytes = gpt_header[12]
    part_table_lbas = (( part_entry_count * part_entry_size_in_bytes ) / LBA_SIZE )
    fbuf = get_lba(f, part_entry_start_lba, part_table_lbas)
    
    return fbuf

def write_part_table_area(f, offset, fbuf):
    f.seek(LBA_SIZE * offset)
    f.write(fbuf)

# I don't know how to use struct.pack with a tuple. Have to read about it
def pack_gpt_header(gpt_header):
    gbuf = struct.pack(GPT_HEADER_FORMAT,gpt_header[0],gpt_header[1],gpt_header[2],gpt_header[3],gpt_header[4],gpt_header[5],gpt_header[6],gpt_header[7],gpt_header[8],gpt_header[9],gpt_header[10],gpt_header[11],gpt_header[12],gpt_header[13])
    return gbuf

def pack_partition_table_entry(part_entry):
    return struct.pack(GUID_PARTITION_ENTRY_FORMAT,part_entry[0],part_entry[1],part_entry[2],part_entry[3],part_entry[4],part_entry[5])

def is_block_device(filename):
	try:
		mode = os.lstat(filename).st_mode
	except OSError:
		return False
	else:
		return stat.S_ISBLK(mode)

def get_block_size_of_device(device):
	if is_block_device(device):
		output = subprocess.Popen(["blockdev", "--getsz", device], stdout=subprocess.PIPE).communicate()[0]
		return int(output)
	else:
		size = os.path.getsize(device)
		blocks = size / LBA_SIZE
		return int(blocks)


def parseArguments():
    parser = argparse.ArgumentParser(description='Move the backup GPT to the end of a device')
    parser.add_argument('--device',nargs=1,required=True,help='Specify the device on which the backup GPT should be moved',dest='device')

    args = parser.parse_args()
    return args

def main():
	args = parseArguments()
	device = args.device[0]
	print 'Determining last block of device'
	lastBlock = get_block_size_of_device(device) 
	#lastBlock = lastBlock - 1
	print 'Last block is %d'%lastBlock

	fbuf = ''
	try:
		print 'Opening device %s'%device
		f = open(device, 'r+b')
	except IOError:
		print 'An IOError occured'
		sys.exit(-1)

	print 'Reading current GPT headers from device'
	primary_gpt_header, primary_crc32_header_value, fbuf = get_gpt_header(f,fbuf, PRIMARY_GPT_LBA)
	secondary_gpt_header, secondary_crc32_header_value, fbuf = get_gpt_header(f,fbuf, primary_gpt_header[6])
	print 'Reading secondary GPT table from device'
	partition_table = get_part_table_area(f, secondary_gpt_header)
	part_table_size =  (( secondary_gpt_header[11] * secondary_gpt_header[12] ) / LBA_SIZE ) 

	print 'Size of the partition table is %d LBA'%part_table_size

	last_usable_lba_for_partitions = lastBlock - ( part_table_size + 2 )

	print 'Last usable LBA for partitions is %d'%last_usable_lba_for_partitions

	primary_gpt_header = list(primary_gpt_header)
	primary_gpt_header[6] = lastBlock - 1
	primary_gpt_header[8] = last_usable_lba_for_partitions
	primary_gpt_header = tuple(primary_gpt_header)

	print 'Updating primary header'
	update_gpt(f,primary_gpt_header)
	
	secondary_gpt_header = list(secondary_gpt_header)
	secondary_gpt_header[5] = lastBlock - 1
	secondary_gpt_header[8] = last_usable_lba_for_partitions
	secondary_gpt_header[10] = lastBlock - ( part_table_size + 1 )
	secondary_gpt_header = tuple(secondary_gpt_header)

	print 'Writing secondary header to end of device'
	update_gpt(f, secondary_gpt_header)

	print 'Beginning of secondary partition table is %d'%secondary_gpt_header[10]
	print 'Writing secondary GPT table'
	write_part_table_area(f, secondary_gpt_header[10], partition_table)

	f.close()


if __name__ == "__main__":
	main()