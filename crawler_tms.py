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
import codecs
import xmltodict
import time
from datetime import timedelta

class MaterialProvider():
    @staticmethod
    def getNaming(fn: str = "") -> str:
        naming: dict = {"ap": dict(), "sta": dict()}
        if os.path.exists(fn) is True:
            with codecs.open(fn, "r", encoding = "utf-8", errors = "ignore") as f:
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
        return naming

    @staticmethod
    def getPermutation(fn: str = "") -> str:
        DELI_PERMUTE = ","
        permutation: dict = dict()
        if os.path.exists(fn) is True:
            with codecs.open(fn, "r", encoding = "utf-8", errors = "ignore") as f:
                m = xmltodict.parse(f.read())
                for prog in m:
                    for tc in m[prog]:
                        if tc not in permutation:
                            permutation[tc] = {"ap": list(), "sta": list()}
                            if "AP" in m[prog][tc] and m[prog][tc]["AP"] is not None and m[prog][tc]["AP"].isdigit() == False:
                                permutation[tc]["ap"] = m[prog][tc]["AP"].split(DELI_PERMUTE)
                            if "STA" in m[prog][tc] and m[prog][tc]["STA"] is not None and m[prog][tc]["STA"].isdigit() == False:
                                permutation[tc]["sta"] = m[prog][tc]["STA"].split(DELI_PERMUTE)
        logging.debug(repr(permutation))
        return permutation

    @staticmethod
    def getMaterial(**kwargs) -> dict:
        for k,v in kwargs.items():
            logging.error("the value of {} is {}".format(k, v))
        return dict()

class TmsCrawler(MaterialProvider):
    @staticmethod
    def getMaterial(**kwargs) -> dict:
        material: dict = dict()
        event: str = kwargs["event"]
        directory: str = kwargs["directory"]
        rst_expected: str = kwargs["rst_expected"]
        account: str = kwargs["account"]
        password: str = kwargs["password"]
        sftp_usr: str = kwargs["sftp_usr"]
        sftp_pwd: str = kwargs["sftp_pwd"]
        since: str = kwargs["since"]
        prefix: str = kwargs["prefix"]
        latest: str = kwargs["latest"]
        cnt: int = 0
        cnt_dl: int = 0
        cnt_omitted: int = 0
        cnt_exec: int = 0
        evaluation_dl_qty: int = 0
        term_early: bool = False
        ftp_fetching: bool = True
        cache_cover: bool = False
        cache_category: bool = False
        cached_directory: str = directory
        cached_cover: str = cached_directory + os.path.sep + "cover.txt"
        cached_category: str = cached_directory + os.path.sep + "category.txt"
        PORTAL: str = "https://tms.wi-fi.org/"
        AUTHENTICATOR: str = "https://tms.wi-fi.org/api/authentication"
        COVER: str = "https://tms.wi-fi.org/api/events/" + event
        CATEGORY: str = "https://tms.wi-fi.org/api/testResults/event/" + event
        INDIVIDUAL: str = "https://tms.wi-fi.org/wifitmsftp/api/ftp-file?"
        with requests.Session() as s:
            os.makedirs(cached_directory, mode = 0o777, exist_ok = True)
            #preparation; retrieve CSRF-TOKEN
            rsp1 = s.get(PORTAL)
            c1:dict = rsp1.cookies.get_dict()
            logging.debug("the cookie of CSRF-TOKEN is \"%s\"" % (c1))
            #preparation; retrieve JSESSIONID
            h2: dict = {"X-CSRF-TOKEN":c1["CSRF-TOKEN"]}
            d2: dict = {"j_username": account, "j_password": password}
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
                    username: str = os.path.basename(js3["ftpUserName"]) if sftp_usr is None else sftp_usr
                    password: str = js3["password"] if sftp_pwd is None else sftp_pwd
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
                    if rmt_path_tc.startswith(prefix) is False:
                        logging.debug("tc \"%s\" is omitted" %(rmt_path_tc))
                        cnt_omitted += 1
                        continue
                    if (len(since) > 0) and (int(since) > int(result["timestamp"])):
                        logging.debug("the tc with ts \"%s\" is old enough to be omitted" % (result["timestamp"]))
                        cnt_omitted += 1
                        continue
                    if (len(permutation) > 0) and (result["testCaseIdName"] not in permutation):
                        logging.debug("the tc %s is NOT in permutation (table)" % (result["testCaseIdName"]))
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
                        if ftp_fetching is True:
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
                                time_begin = time.time()
                                conn5.get(remotepath=rmt_path, localpath=lcl_path, preserve_mtime=False)
                                time_end = time.time()
                                time_diff = time_end - time_begin
                                logging.info("lcl_path \"%s\" is downloaded (within %d seconds)" % (lcl_path, timedelta(seconds=time_diff).total_seconds()))
                                cnt_dl += 1
                                if evaluation_dl_qty > 0 and evaluation_dl_qty <= cnt_dl:
                                    term_early = True
                        else:
                            #process; fetch log from web site
                            url: str = INDIVIDUAL + "homePath=" + js3["ftpUserName"] + "&" + "uri=" + result["logFileName"]
                            logging.info("url is \"%s\"" % (url))
                            #process; check log existence on web site
                            time_begin = time.time()
                            rsp5 = s.get(url, headers=h3)
                            if rsp5.status_code == 200:
                                with open(lcl_path, "wb") as f5:
                                    f5.write(rsp5.content)
                                time_end = time.time()
                                time_diff = time_end - time_begin
                                logging.info("lcl_path \"%s\" is downloaded (within %d seconds)" % (lcl_path, timedelta(seconds=time_diff).total_seconds()))
                            else:
                                logging.info("lcl_path \"%s\" is unable to be downloaded" % (lcl_path))
                                cnt_omitted += 1
                                continue
                            cnt_dl += 1
                            if evaluation_dl_qty > 0 and evaluation_dl_qty <= cnt_dl:
                                term_early = True
                    logging.debug(result)
                    candidate: dict = dict()
                    candidate["timestamp"] = result["timestamp"]
                    candidate["path"] = lcl_path
                    if rmt_path_tc not in material:
                        material[rmt_path_tc] = list()
                    append: bool = True
                    if latest is True:
                        for i,c in enumerate(material[rmt_path_tc]):
                            if (int(candidate["timestamp"]) > int(c["timestamp"])):
                                logging.info("the tc with ts \"%s\" is NOT the latest and it should be excluded" % (c["timestamp"]))
                                material[rmt_path_tc].pop(i)
                                cnt_omitted += 1
                                cnt_exec -= 1
                                break
                            else:
                                logging.info("the tc with ts \"%s\" is NOT the latest and it should NOT be kept" % (candidate["timestamp"]))
                                cnt_omitted += 1
                                cnt_exec -= 1
                                append = False
                    if append is True:
                        logging.debug("the tc with ts \"%s\" is going to be executed (%d)" % (candidate["timestamp"], len(material[rmt_path_tc])))
                        material[rmt_path_tc].append(candidate)
                    cnt_exec += 1
                    if term_early is True:
                        break
            logging.info("the iterated count is %d" % (cnt))
            logging.info("the executed count is %d" % (cnt_exec))
            logging.info("the downloaded count is %d" % (cnt_dl))
            logging.info("the omitted count is %d" % (cnt_omitted))
            logging.info("the quantity of results is %d" % (len(js4)))
            logging.info(repr(material))
        return material

class MaterialDecorator():
    @staticmethod
    def decorate(**kwargs) -> dict:
        for k,v in kwargs.items():
            logging.error("the value of {} is {}".format(k, v))
        return dict()

class UccLogParser(MaterialDecorator):
    @staticmethod
    def decorate(**kwargs) -> dict:
        return UccLogParser.parse(**kwargs)

    @staticmethod
    def parse(**kwargs) -> dict:
        material: str = kwargs["material"]
        category: str = kwargs["category"]
        fn_patt6 = re.compile(r"(?!sniffer).*(\D\D\D)-[0-9]+\.[0-9]*\.*[0-9]*.*\.log")
        for tc in material:
            kept: bool = True
            for idx, candidate in enumerate(material[tc]):
                tmp_dir: str = os.path.dirname(candidate["path"])
                tmp_fn: str = os.path.basename(candidate["path"])
                ucc_log_path: str = ""
                if zipfile.is_zipfile(candidate["path"]):
                    logging.debug("Archive format is %s; %s" % ("zip", candidate["path"]))
                    with zipfile.ZipFile(candidate["path"], "r") as archive:
                        allfiles = archive.namelist()
                        selected = [f for f in allfiles if fn_patt6.match(f)]
                        for fn in selected:
                            archive.getinfo(fn).filename = tmp_fn + "-" + fn
                            archive.extract(member=fn, path=tmp_dir)
                            ucc_log_path = tmp_dir + os.path.sep + archive.getinfo(fn).filename
                else:
                    logging.info("the file %s is NOT a zipfile (or broken)" % (candidate["path"]))
                verdict: dict = {"core_ver": None, "elapsed": None, "result": None, "dut": None, "ap": list(), "sta": list()}
                if os.path.exists(ucc_log_path) is True:
                    with codecs.open(ucc_log_path, "r", encoding = "utf-8", errors = "ignore") as f:
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
                            if verdict["dut"] is None:
                                capi_patt5: str = re.compile(r"DUT \(.*\)\s+<--\s+status,(.+),vendor,(.+),model,(.+),version,(.+)")
                                if re.search(capi_patt5, line) is not None:
                                    capi_patt5d: str = r"INFO - DUT \(.*\)\s+<--\s+status,(.+),vendor,(.+),model,(.+),version,(.+)"
                                    capi_patt5p: str = r"INFO - parallel.* DUT \(.*\)\s+<--\s+status,(.+),vendor,(.+),model,(.+),version,(.+)"
                                    if re.search(capi_patt5p, line) is not None:
                                        capi_patt5d = capi_patt5p
                                    matched_result = re.findall(capi_patt5d, line)
                                    if matched_result is not None and len(matched_result) > 0 and len(matched_result[0]) > 0:
                                        verdict["dut"] = matched_result[0][1]
                                        continue
                            #multiple time check
                            capi_patt6: str = re.compile(r".*--->.*_set_security")
                            if re.search(capi_patt6, line) is not None:
                                capi_patt6ap: str = None
                                capi_patt6sta: str = None
                                capi_patt6p: str = re.compile(r"parallel.*--->.*_set_security")
                                if re.search(capi_patt6p, line) is not None:
                                    capi_patt6ap: str = r"INFO - parallel.* (.*?) \(.*\)\s+--->\s+ap_set_security"
                                    capi_patt6sta: str = r"INFO - parallel.*  (.*?) \(.*\)\s+--->\s+sta_set_security"
                                else:
                                    capi_patt6ap: str = r"INFO - (.*?) \(.*\)\s+--->\s+ap_set_security"
                                    capi_patt6sta: str = r"INFO - (.*?) \(.*\)\s+--->\s+sta_set_security"
                                matched_ap_name = re.findall(capi_patt6ap, line)
                                if matched_ap_name is not None and len(matched_ap_name) > 0:
                                    ap_name = matched_ap_name[0] if matched_ap_name[0] != "DUT" else None
                                    if ap_name not in verdict["ap"] and ap_name is not None:
                                        verdict["ap"].append(ap_name)
                                        continue
                                matched_sta_name = re.findall(capi_patt6sta, line)
                                if matched_sta_name is not None and len(matched_sta_name) > 0:
                                    sta_name = matched_sta_name[0] if matched_sta_name[0] != "DUT" else None
                                    if sta_name not in verdict["sta"] and sta_name is not None:
                                        verdict["sta"].append(sta_name)
                                        continue
                else:
                    logging.info("there is no UCC log in zipfile %s" %(candidate["path"]))
                    kept = False
                if kept is False:
                    material[tc].pop(idx)
                    logging.info("the candidate with index %d is excluded" %(idx))
                else:
                    material[tc][idx]["ap"] = verdict["ap"]
                    material[tc][idx]["sta"] = verdict["sta"]
                    material[tc][idx]["dut"] = verdict["dut"]
                    material[tc][idx]["elapsed"] = verdict["elapsed"]
                    logging.info("the candidate with index %d is included" %(idx))
            logging.debug(repr(material))
            if (category == "first") or (category == "last"):
                remedied: set = set()
                for idx, candidate in enumerate(material[tc]):
                    for i, c in enumerate(material[tc]):
                        if i == idx:
                            continue
                        if "dut" in c and c["dut"] == candidate["dut"]:
                            if ("ap" not in c) or ("sta" not in c) or ("timestamp" not in c):
                                logging.info("parameter is missing")
                                continue
                            elif (c["ap"] != candidate["ap"]) or (c["sta"] != candidate["sta"]):
                                logging.info("permutation is different")
                                continue
                            else:
                                if (category == "last"):
                                    if (int(c["timestamp"]) >= int(candidate["timestamp"])):
                                        logging.info("the timestamp of candidate %d is not \"greater than or equal to\" existing" % (idx))
                                        remedied.add(idx)
                                        continue
                                elif (args.category == "first"):
                                    if (int(c["timestamp"]) < int(candidate["timestamp"])):
                                        logging.info("the timestamp of candidate %d is not \"less than\" existing" % (idx))
                                        remedied.add(idx)
                                        continue
                                else:
                                    pass
                if len(remedied) > 0:
                    for r in remedied:
                        material[tc].pop(r)
        logging.debug(repr(material))
        return material

class MaterialSerializer():
    @staticmethod
    def serialize(**kwargs) -> str:
        for k,v in kwargs.items():
            logging.error("the value of {} is {}".format(k, v))
        return ""

class ReportFormatter(MaterialSerializer):
    @staticmethod
    def serialize(**kwargs) -> str:
        finished: str = ""
        material = kwargs["material"]
        naming = kwargs["naming"]
        permutation = kwargs["permutation"]
        rst_expected: str = kwargs["rst_expected"]
        delimiter: str = kwargs["delimiter"]
        DELI_OUTER: str = "; "
        DELI_INNER: str = ","
        DELI_ENCLOSED_LHS: str = "["
        DELI_ENCLOSED_RHS: str = "]"
        DELI_MISMATCHED: str = "*"
        DELI_PERMUTED: str = "M"
        DELI_UNPERMUTED: str = ""
        for tc in material:
            permuted: bool = True if tc in permutation else False
            for idx, candidate in enumerate(material[tc]):
                rst: str = rst_expected + DELI_OUTER
                rst += tc + DELI_OUTER
                rst += ("%d" % (candidate["timestamp"])) + DELI_OUTER
                rst += ("%s" % (candidate["elapsed"] if "elapsed" in candidate else "")) + DELI_OUTER
                rst += ("%s" % (candidate["dut"] if "dut" in candidate else "")) + DELI_OUTER
                ap: str = ""
                ap += DELI_ENCLOSED_LHS
                if "ap" in candidate:
                    for i,c in enumerate(candidate["ap"]):
                        if i > 0:
                            ap += DELI_INNER
                        a: str = c
                        if ("ap" in naming and c in naming["ap"]):
                            a = naming["ap"][c]
                        if permuted is True:
                            if (len(candidate["ap"]) == len(permutation[tc]["ap"])) and (i < len(permutation[tc]["ap"])) and (a == permutation[tc]["ap"][i]):
                                ap += a
                            else:
                                ap += a + DELI_MISMATCHED
                        else:
                            ap += a
                ap += DELI_ENCLOSED_RHS
                rst += ap + DELI_OUTER
                sta: str = ""
                sta += DELI_ENCLOSED_LHS
                if "sta" in candidate:
                    for i,c in enumerate(candidate["sta"]):
                        if i > 0:
                            sta += DELI_INNER
                        s: str = c
                        if ("sta" in naming and c in naming["sta"]):
                            s = naming["sta"][c]
                        if permuted is True:
                            if (len(candidate["sta"]) == len(permutation[tc]["sta"])) and (i < len(permutation[tc]["sta"])) and (s == permutation[tc]["sta"][i]):
                                sta += s
                            else:
                                sta += s + DELI_MISMATCHED
                        else:
                            sta += s
                sta += DELI_ENCLOSED_RHS
                rst += sta + DELI_OUTER
                rst += DELI_PERMUTED if permuted is True else DELI_UNPERMUTED
                finished += (delimiter if len(finished) > 0 else "") + rst
        return finished

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
    my_parser.add_argument("-l",
        "--latest",
        action="store_true",
        help="Latest one only")
    my_parser.add_argument("-y",
        "--category",
        metavar="category",
        default="all",
        choices=["all", "first", "last"],
        type=str,
        help="category of log")
    my_parser.add_argument("-n",
        "--naming",
        metavar="naming",
        default="",
        type=str,
        help="The path of testbed naming file (i.e DisplayNames.txt)")
    my_parser.add_argument("-m",
        "--permute",
        metavar="permute",
        default="",
        type=str,
        help="The path of testbed permutation file (i.e MasterTestInfo.xml)")
    my_parser.add_argument("-r",
        "--result",
        metavar="result",
        default="Pass",
        choices=["Fail", "Pass"],
        type=str,
        help="the expected result")
    my_parser.add_argument("-d",
        "--directory",
        metavar="directory",
        default="tmp",
        type=str,
        help="directory of UCC log and capture")
    my_parser.add_argument(
        "--sftp-usr",
        metavar="sftp_usr",
        default=None,
        type=str,
        help="alternative SFTP username")
    my_parser.add_argument(
        "--sftp-pwd",
        metavar="sftp_pwd",
        default=None,
        type=str,
        help="alternative SFTP password")
    my_parser.add_argument("-o",
        "--offline",
        action="store_true",
        help="offline")

    args = my_parser.parse_args()
    if args.verbose == True :
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.ERROR)
    logging.debug("args: " + repr(args))

    naming = MaterialProvider.getNaming(args.naming)
    permutation = MaterialProvider.getPermutation(args.permute)

    material: dict = dict()
    if args.offline is False:
        material = TmsCrawler.getMaterial(event = args.event,
            directory = args.directory,
            rst_expected = args.result,
            account = args.account,
            password = args.password,
            sftp_usr = args.sftp_usr,
            sftp_pwd = args.sftp_pwd,
            since = args.since,
            prefix = args.prefix,
            latest = args.latest,
            permutation = permutation)
    else:
        pass

    #process; retrieve testbed names from the UCC log
    decorated: dict = UccLogParser.decorate(material = material,
        category = args.category)

    #finalize; output report
    rst: str = ReportFormatter.serialize(material = decorated,
        naming = naming,
        permutation = permutation,
        rst_expected = args.result,
        delimiter = os.linesep)
    print(rst)

#Crawler6 - by Leo Liu
