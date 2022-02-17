# getSwitchERR
Quick script to iterate through all available switches and output switches with CRC errors on uplink ports

TO RUN:
1. (FIRST TIME ONLY) run ./create_keys.py to generate a keyfile for your API, only have to do it once
2. (OPTIONAL) If you enter your org_id in the 'org_whitelist.txt' file, it'll only run against those orgs otherwise it'll do everything you have access to
3. run ./getSwitchERR.py and it'll output to files "switch_CRC_errors.txt" and "switch_CRC_errors.json" with the results

