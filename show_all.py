import argparse

from gpt_lib import GPT_Entry
from gpt_lib import GPT_Header 
from gpt_lib import BlockDev
from gpt_lib import GPT

def parseArguments():
    parser = argparse.ArgumentParser(description='Show useful infos about a disk(image)')
    parser.add_argument('--disk',nargs=1,required=True,help='Specify the disk(image)',dest='disk')

    args = parser.parse_args()
    return args

def main():
	args = parseArguments()
	device = BlockDev(args.disk[0])
	gpt = GPT(device)

	primary_header = gpt.get_gpt_header()
	secondary_header = gpt.get_gpt_header(True)

	primary_table_entries = gpt.get_table()
	secondary_table_entries = gpt.get_table(True)

	primary_header_checksum = gpt._calc_header_crc32(primary_header.serialize())
	secondary_header_checksum = gpt._calc_header_crc32(secondary_header.serialize())

	primary_table_checksum = gpt._calc_table_crc32(gpt_entries=primary_table_entries)
	secondary_table_checksum = gpt._calc_table_crc32(gpt_entries=secondary_table_entries)

	if primary_header.header_checksum != primary_header_checksum:
		print '[WARNING] Checksum mismatch for primary header:'
		print '\t Expected: %.8x'%primary_header.header_checksum
		print '\t Calculated: %.8x'%primary_header_checksum

	if secondary_header.header_checksum != secondary_header_checksum:
		print '[WARNING] Checksum mismatch for secondary header'
		print '\t Expected: %.8x'%secondary_header.header_checksum
		print '\t Calculated: %.8x'%secondary_header_checksum

	if primary_header.table_checksum != primary_table_checksum:
		print '[WARNING] Checksum mismatch for primary table'
		print '\t Expected: %.8x'%primary_header.table_checksum
		print '\t Calculated: %.8x'%primary_table_checksum

	if secondary_header.table_checksum != secondary_table_checksum:
		print '[WARNING] Checksum mismatch for secondary table'
		print '\t Expected: %.8x'%secondary_header.table_checksum
		print '\t Calculated: %.8x'%secondary_table_checksum

	print 'Start of primary table: %d'%primary_header.table_start_lba
	print 'Position of secondary header: %d'%primary_header.other_offset

	for entry in primary_table_entries:
		print '[PARTITION] Name: %s'%entry.name
		print '\t Start LBA: %d'%entry.first_lba
		print '\t Size: %d'%(entry.last_lba - entry.first_lba)

if __name__ == "__main__":
	main()