#! python3

import os
import sys
import argparse
import logging
import requests
import json

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

    args = my_parser.parse_args()
    if args.verbose == True :
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.ERROR)
    logging.debug("args: " + repr(args))

    cache_cover: bool = False
    cache_category: bool = False
    cached_cover: str = "cover.txt"
    cached_category: str = "category.txt"
    PORTAL: str = "https://tms.wi-fi.org/"
    AUTHENTICATOR: str = "https://tms.wi-fi.org/api/authentication"
    COVER: str = "https://tms.wi-fi.org/api/events/" + args.event
    CATEGORY: str = "https://tms.wi-fi.org/api/testResults/event/" + args.event
    INDIVIDUAL: str = "https://tms.wi-fi.org/wifitmsftp/api/ftp-file?"
    with requests.Session() as s:
        #preparation; retrieve CSRF-TOKEN
        rsp1 = s.get(PORTAL)
        c1:dict = rsp1.cookies.get_dict()
        logging.info(c1)
        print("CSRF-TOKEN: %s" % (c1["CSRF-TOKEN"]))
        #preparation; retrieve JSESSIONID
        h2: dict = {"X-CSRF-TOKEN":c1["CSRF-TOKEN"]}
        d2: dict = {"j_username": args.account, "j_password": args.password}
        rsp2 = s.post(AUTHENTICATOR, headers=h2, data=d2)
        c2:dict = rsp2.cookies.get_dict()
        logging.info(c2)
        print("JSESSIONID: %s" % (c2["JSESSIONID"]))
        #process; retrieve event related information such as name/password/ftpUserName
        h3: dict = {"JSESSIONID": c2["JSESSIONID"]}
        rsp3 = s.get(COVER, headers=h3)
        if cache_cover is True:
            with open(cached_cover, "wb") as f3:
                f3.write(rsp3.text.encode("utf-8"))
        js3 = json.loads(rsp3.text)
        logging.info(js3["id"])
        logging.info(js3["name"])
        logging.info(js3["password"])
        logging.info(js3["ftpUserName"])
        rsp4 = s.get(CATEGORY, headers=h3)
        if cache_category is True:
            with open(cached_category, "wb") as f4:
                f4.write(rsp4.text.encode("utf-8"))
        js4 = json.loads(rsp4.text)
        for result in js4:
            logging.info(result)
            logging.info(result["id"])
            logging.info(result["result"])
            logging.info(result["logFileName"])
            if result["result"] == "Pass":
                url: str = INDIVIDUAL + "homePath=" + js3["ftpUserName"] + "&" + "uri=" + result["logFileName"]
                print("url: %s" % (url))
                #TODO: process; fetch log from either FTP site or web site
                #break

#Crawler6 - by Leo Liu
