#! python3

import os
import sys
import argparse
import logging
import requests
import json
import warnings
import pysftp

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
        help="Event number")
    my_parser.add_argument("-a",
        "--account",
        metavar="account",
        default="",
        type=str,
        help="Account")
    my_parser.add_argument("-p",
        "--password",
        metavar="password",
        default="",
        type=str,
        help="Password")
    my_parser.add_argument("-x",
        "--prefix",
        metavar="prefix",
        default="",
        type=str,
        help="Permitted prefix of test case")

    args = my_parser.parse_args()
    if args.verbose == True :
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.ERROR)
    logging.debug("args: " + repr(args))

    rst_expected: str = "Pass"
    cnt: int = 0
    cnt_dl: int = 0
    cnt_omitted: int = 0
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
                lcl_dir: str = cached_directory + os.path.sep + rmt_path_dir
                if os.path.exists(lcl_dir) is False:
                    os.makedirs(lcl_dir, mode = 0o777, exist_ok = True)
                lcl_path: str = lcl_dir + os.path.sep + rmt_path_fn
                logging.debug("lcl_path is \"%s\"" %(lcl_path))
                if os.path.exists(lcl_path) is True:
                    logging.info("lcl_path \"%s\" is existing" % (lcl_path))
                    cnt_omitted += 1
                    continue
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
                if term_early is True:
                    break
        logging.info("the executed count is %d" % (cnt))
        logging.info("the omitted count is %d" % (cnt_omitted))
        logging.info("the quantity of results is %d" % (len(js4)))

#Crawler6 - by Leo Liu
