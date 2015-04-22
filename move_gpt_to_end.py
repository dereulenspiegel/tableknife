from gpt_lib import GPT_Entry
from gpt_lib import GPT_Header 
from gpt_lib import BlockDev
from gpt_lib import GPT

def main():
	device = BlockDev('gpt_full.img')
	gpt = GPT(device)

	primary_header = gpt.get_gpt_header()
	secondary_header = gpt.get_gpt_header(True)

	gpt_entries = gpt.get_table()

	block_size = device.get_block_count()
	print 'Determined block_size of %d blocks'%block_size

	secondary_header_offset = block_size - 1
	secondary_table_offset = block_size - 33
	last_usable_lba = block_size - 34

	primary_header.last_usable_lba = last_usable_lba
	secondary_header.last_usable_lba = last_usable_lba

	primary_header.other_offset = secondary_header_offset
	secondary_header.own_offset = secondary_header_offset
	secondary_header.table_start_lba = secondary_table_offset

	gpt.write_gpt(primary_header, gpt_entries)
	gpt.write_gpt(secondary_header, gpt_entries)

	device.close()

if __name__ == "__main__":
	main()