#! python3

import os
import sys
import argparse
import logging
import requests
import json
import warnings
import pysftp
import zipfile
import re

if __name__ == "__main__":
    my_parser = argparse.ArgumentParser(description="CLI argument parsing")
    my_parser.add_argument("-v",
        "--verbose",
        action="store_true",
        help="verbosity")
    my_parser.add_argument("-e",
        "--event",
        metavar="event",
        default="",
        type=str,
        help="Event number",
        required=True)
    my_parser.add_argument("-a",
        "--account",
        metavar="account",
        default="",
        type=str,
        help="Account",
        required=True)
    my_parser.add_argument("-p",
        "--password",
        metavar="password",
        default="",
        type=str,
        help="Password",
        required=True)
    my_parser.add_argument("-x",
        "--prefix",
        metavar="prefix",
        default="",
        type=str,
        help="Permitted prefix of test case")
    my_parser.add_argument("-s",
        "--since",
        metavar="since",
        default="",
        type=str,
        help="Since the specified timestamp (in milliseconds)")
    my_parser.add_argument("-n",
        "--naming",
        metavar="naming",
        default="",
        type=str,
        help="The path of testbed naming file (i.e DisplayNames.txt)")

    args = my_parser.parse_args()
    if args.verbose == True :
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.ERROR)
    logging.debug("args: " + repr(args))

    naming: dict = {"ap": dict(), "sta": dict()}
    if os.path.exists(args.naming) is True:
        with open(args.naming) as f:
            for line in f:
                n = line.strip().split("!")
                if len(n) == (3 + 1):
                    matched_name_ap = re.findall(r"wfa_control_agent_(.*?)_ap", n[1])
                    if matched_name_ap is not None and len(matched_name_ap) > 0:
                        naming["ap"][n[2]] = matched_name_ap[0]
                        continue
                    matched_name_sta = re.findall(r"wfa_control_agent_(.*?)_sta", n[1])
                    if matched_name_sta is not None and len(matched_name_sta) > 0:
                        naming["sta"][n[2]] = matched_name_sta[0]
                        continue
    logging.debug(repr(naming))

    material: dict = dict()
    rst_expected: str = "Pass"
    cnt: int = 0
    cnt_dl: int = 0
    cnt_omitted: int = 0
    cnt_exec: int = 0
    evaluation_dl_qty: int = 0
    term_early: bool = False
    cache_cover: bool = False
    cache_category: bool = False
    cached_directory: str = "tmp"
    cached_cover: str = cached_directory + os.path.sep + "cover.txt"
    cached_category: str = cached_directory + os.path.sep + "category.txt"
    PORTAL: str = "https://tms.wi-fi.org/"
    AUTHENTICATOR: str = "https://tms.wi-fi.org/api/authentication"
    COVER: str = "https://tms.wi-fi.org/api/events/" + args.event
    CATEGORY: str = "https://tms.wi-fi.org/api/testResults/event/" + args.event
    INDIVIDUAL: str = "https://tms.wi-fi.org/wifitmsftp/api/ftp-file?"
    with requests.Session() as s:
        os.makedirs(cached_directory, mode = 0o777, exist_ok = True)
        #preparation; retrieve CSRF-TOKEN
        rsp1 = s.get(PORTAL)
        c1:dict = rsp1.cookies.get_dict()
        logging.debug("the cookie of CSRF-TOKEN is \"%s\"" % (c1))
        #preparation; retrieve JSESSIONID
        h2: dict = {"X-CSRF-TOKEN":c1["CSRF-TOKEN"]}
        d2: dict = {"j_username": args.account, "j_password": args.password}
        rsp2 = s.post(AUTHENTICATOR, headers=h2, data=d2)
        c2:dict = rsp2.cookies.get_dict()
        logging.debug("the cookie of JSESSIONID is \"%s\"" %(c2))
        #process; retrieve event related information such as name/password/ftpUserName
        h3: dict = {"JSESSIONID": c2["JSESSIONID"]}
        rsp3 = s.get(COVER, headers=h3)
        if cache_cover is True:
            with open(cached_cover, "wb") as f3:
                f3.write(rsp3.text.encode("utf-8"))
        js3 = json.loads(rsp3.text)
        logging.debug("event identifier is %s" % (js3["id"]))
        logging.debug("event name is %s" % (js3["name"]))
        logging.debug("event password is %s" % (js3["password"]))
        logging.debug("ftp home directory is %s" % (js3["ftpUserName"]))
        rsp4 = s.get(CATEGORY, headers=h3)
        if cache_category is True:
            with open(cached_category, "wb") as f4:
                f4.write(rsp4.text.encode("utf-8"))
        js4 = json.loads(rsp4.text)
        for result in js4:
            cnt += 1
            logging.debug("id is %s" %(result["id"]))
            logging.debug("result is %s" %(result["result"]))
            logging.debug("timestamp is %s" %(result["timestamp"]))
            logging.debug("log file name is %s" %(result["logFileName"]))
            if result["result"] == rst_expected:
                username: str = os.path.basename(js3["ftpUserName"])
                password: str = js3["password"]
                path_full: str = result["logFileName"]
                host: str = path_full.lstrip("ftp://").split("/")[0]
                logging.debug("host is %s" % (host))
                rmt_path: str = path_full.lstrip("ftp://").lstrip(host).lstrip("/")
                logging.debug("rmt_path is \"%s\"" % (rmt_path))
                rmt_path_dir: str = os.path.dirname(rmt_path)
                logging.debug("rmt_path_dir is \"%s\"" % (rmt_path_dir))
                rmt_path_fn: str = os.path.basename(rmt_path)
                logging.debug("rmt_path_fn is \"%s\"" %(rmt_path_fn))
                rmt_path_tc: str = os.path.basename(rmt_path_dir)
                logging.debug("rmt_path_tc is \"%s\"" %(rmt_path_tc))
                if rmt_path_tc.startswith(args.prefix) is False:
                    logging.debug("tc \"%s\" is omitted" %(rmt_path_tc))
                    cnt_omitted += 1
                    continue
                if (len(args.since) > 0) and (int(args.since) > int(result["timestamp"])):
                    logging.debug("the tc with ts \"%s\" is old enough to be omitted" %(result["timestamp"]))
                    cnt_omitted += 1
                    continue
                lcl_dir: str = cached_directory + os.path.sep + rmt_path_dir
                if os.path.exists(lcl_dir) is False:
                    os.makedirs(lcl_dir, mode = 0o777, exist_ok = True)
                lcl_path: str = lcl_dir + os.path.sep + rmt_path_fn
                logging.debug("lcl_path is \"%s\"" %(lcl_path))
                if os.path.exists(lcl_path) is True:
                    logging.info("lcl_path \"%s\" is existing" % (lcl_path))
                else:
                    #process; fetch log from FTP site
                    warnings.filterwarnings("ignore")
                    cnopts = pysftp.CnOpts()
                    cnopts.hostkeys = None
                    with pysftp.Connection(host=host, port=22, username=username, password=password, cnopts=cnopts) as conn5:
                        logging.debug("connection established successfully")
                        #process; check log existence on FTP site
                        pwd5: str = conn5.pwd
                        logging.debug("current working directory is: %s" % (pwd5))
                        if conn5.exists(rmt_path) is False:
                            logging.info("rmt_path \"%s\" is NOT existing" % (rmt_path))
                            cnt_omitted += 1
                            continue
                        #process; fetch log from FTP site to local path
                        conn5.get(remotepath=rmt_path, localpath=lcl_path, preserve_mtime=False)
                        logging.info("lcl_path \"%s\" is downloaded" % (lcl_path))
                        cnt_dl += 1
                        if evaluation_dl_qty > 0 and evaluation_dl_qty <= cnt_dl:
                            term_early = True
                logging.debug(result)
                candidate: dict = dict()
                candidate["timestamp"] = result["timestamp"]
                candidate["path"] = lcl_path
                if rmt_path_tc not in material:
                    material[rmt_path_tc] = list()
                material[rmt_path_tc].append(candidate)
                cnt_exec += 1
                if term_early is True:
                    break
        logging.info("the iterated count is %d" % (cnt))
        logging.info("the executed count is %d" % (cnt_exec))
        logging.info("the downloaded count is %d" % (cnt_dl))
        logging.info("the omitted count is %d" % (cnt_omitted))
        logging.info("the quantity of results is %d" % (len(js4)))
        #process; retrieve testbed names from the UCC log
        fn_patt6 = re.compile(r"(?!sniffer).*(\D\D\D)-[0-9]\.[0-9]*\.[0-9]*.*\.log")
        for tc in material:
            for idx, candidate in enumerate(material[tc]):
                tmp_dir: str = os.path.dirname(candidate["path"])
                tmp_fn: str = ""
                if zipfile.is_zipfile(candidate["path"]):
                    logging.debug("Archive format is %s; %s" % ("zip", candidate["path"]))
                    with zipfile.ZipFile(candidate["path"], "r") as archive:
                        allfiles = archive.namelist()
                        selected = [f for f in allfiles if fn_patt6.match(f)]
                        for fn in selected:
                            archive.extract(member=fn, path=tmp_dir)
                            tmp_fn = tmp_dir + os.path.sep + fn
                verdict: dict = {"core_ver": None, "elapsed": None, "result": None, "ap": list(), "sta": list()}
                if os.path.exists(tmp_fn) is True:
                    with open(tmp_fn) as f:
                        for line in f:
                            #one time check
                            if verdict["core_ver"] is None:
                                matched_core_ver = re.findall(r"WiFiTestSuite Version \[(.*?)\]", line)
                                if matched_core_ver is not None:
                                    verdict["core_ver"] = matched_core_ver[0] if len(matched_core_ver) > 0 else None
                            if verdict["elapsed"] is None:
                                matched_elapsed = re.findall(r"Execution Time \[(.*?)\]", line)
                                if matched_elapsed is not None:
                                    verdict["elapsed"] = matched_elapsed[0] if len(matched_elapsed) > 0 else None
                            if verdict["result"] is None:
                                matched_result = re.findall(r"FINAL TEST RESULT\s+--->\s+(.+)", line)
                                if matched_result is not None:
                                    verdict["result"] = matched_result[0] if len(matched_result) > 0 else None
                            #multiple time check
                            capi_patt6: str = re.compile(r".*--->.*_set_security")
                            if re.search(capi_patt6, line) is not None:
                                matched_ap_name = re.findall(r"INFO - (.*?) \(.*\)\s+--->\s+ap_set_security", line)
                                if matched_ap_name is not None and len(matched_ap_name) > 0:
                                    ap_name = matched_ap_name[0] if matched_ap_name[0] != "DUT" else None
                                    if ap_name not in verdict["ap"] and ap_name is not None:
                                        verdict["ap"].append(ap_name)
                                        continue
                                matched_sta_name = re.findall(r"INFO - (.*?) \(.*\)\s+--->\s+sta_set_security", line)
                                if matched_sta_name is not None and len(matched_sta_name) > 0:
                                    sta_name = matched_sta_name[0] if matched_sta_name[0] != "DUT" else None
                                    if sta_name not in verdict["sta"] and sta_name is not None:
                                        verdict["sta"].append(sta_name)
                                        continue
                logging.debug(repr(verdict))
                material[tc][idx]["ap"] = verdict["ap"]
                material[tc][idx]["sta"] = verdict["sta"]
        logging.debug(repr(material))
        #finalize; output report
        DELI_OUTER: str = "; "
        DELI_INNER: str = ","
        DELI_ENCLOSED_LHS: str = "["
        DELI_ENCLOSED_RHS: str = "]"
        for tc in material:
            for idx, candidate in enumerate(material[tc]):
                rst: str = result["result"] + DELI_OUTER
                rst += tc + DELI_OUTER
                rst += ("%d" % (candidate["timestamp"])) + DELI_OUTER
                ap: str = ""
                ap += DELI_ENCLOSED_LHS
                for i,c in enumerate(candidate["ap"]):
                    if i > 0:
                        ap += DELI_INNER
                    ap += naming["ap"][c] if ("ap" in naming and c in naming["ap"]) else c
                ap += DELI_ENCLOSED_RHS
                rst += ap + DELI_OUTER
                sta: str = ""
                sta += DELI_ENCLOSED_LHS
                for i,c in enumerate(candidate["sta"]):
                    if i > 0:
                        sta += DELI_INNER
                    sta += naming["sta"][c] if ("sta" in naming and c in naming["sta"]) else c
                sta += DELI_ENCLOSED_RHS
                rst += sta + DELI_OUTER
                print("%s" % (rst))

#Crawler6 - by Leo Liu
