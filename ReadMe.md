# Crawler6
---

## Usage:

```sh
usage: crawler_tms.py [-h] [-v] -e event -a account -p password [-x prefix] [-s since] [-l] [-n naming] [-m permute]

CLI argument parsing

options:
  -h, --help            show this help message and exit
  -v, --verbose         verbosity
  -e event, --event event
                        Event number
  -a account, --account account
                        Account
  -p password, --password password
                        Password
  -x prefix, --prefix prefix
                        Permitted prefix of test case
  -s since, --since since
                        Since the specified timestamp (in milliseconds)
  -l, --latest          Latest one only
  -n naming, --naming naming
                        The path of testbed naming file (i.e DisplayNames.txt)
  -m permute, --permute permute
                        The path of testbed permutation file (i.e MasterTestInfo.xml)
```

Note: **pysftp** and **xmltodict** packages should be installed (before running).


## Description:

A utility (tool) to reprocess the report of WFA TMS service.
TMS is a web service with corresponding user interface; end-user could verify the report for specific event on the web page, download the actual UCC log (Zip archive), and dive into the UCC log for knowing what testbeds are used. The web page is a matrix styled representation for device-under-test and primary testbed pair.
Current representation of TMS could not fulfill for the test case required more than one/primary testbeds; such representation could not know whether the testbed permutation is matching with the profile specific files (i.e. _DisplayNames.txt_ & _MasterTestInfo.xml_), too. Besides, the user interface is not friendly enough for bulk logs downloading.
This utility is designed to automatically reprocess the raw report of TMS API output, download each pass logs via SFTP, and compare/match the profile specific files, then, a reprocessed report with the testbed permutation could be generated accordingly.

