Table Knife
===========
This small utility allows you to put a binary payload between the GPT Header and the partition table entries. 

Why is this necessary? 
----------------------
Some ARM based SoCs like the Freescale imx6 expect an IVT at position 1024 (in Bytes) in which the position of the next stage bootloader and other things are specified. In the past this wasn't a problem since a traditional MBR partition table only takes up the first two LBA (based on 512 bytes sector size). But a GPT (GUID Partition Table) allows for much more partition table entries so the GPT takes up up to 34 LBAs (again based on a block size of 512 bytes). This means that the SoC would try to interpret the first few bytes of the first partition table entry as its IVT.
Luckily the GPT specifications allows you to specify the start of partition table entries in the header. We are using this to move the partition table back on the disk, so we can put a binary payload (like the IVT or even a complete bootloader) between the GPT header in LBA 2 and the partition table entries.

Usage
-----
`python gpt.py --disk /path/to/disk(image) --payload ./path/to/payload --part-num [partition number]`

* --disk specifies the path to the disk or disk image you want to modify
* --payload specifies the path to the binary payload you want to between between GPT header and partition table entries
* --part-num specifies the number of the first partition after the partition table entries. I the future we should discover this automatically. 

Optional you can specify the parameter --skip which lets you skip a certain amount of bytes of the binary payload.

Issues
------
* Discover the first partition automatically
* Sanity checks if the first partition needs to be resized or not
* Code cleanup