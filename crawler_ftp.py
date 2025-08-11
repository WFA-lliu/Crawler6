#! python3
import os
import sys
import argparse
import logging
import warnings
import pysftp
import zipfile
import re
import codecs
import time
from datetime import datetime
from datetime import timedelta

class FtpCrawler():
    DIR_SEP: str = "/"
    def __init__(self, host: str = None, port: int = None, usr: str = None, pwd: str = None) -> None:
        self.host = ""
        self.port = int(22)
        self.usr = ""
        self.pwd = ""
        if host is not None:
            self.host = host
        if port is not None:
            self.port = port
        if usr is not None:
            self.usr = usr
        if pwd is not None:
            self.pwd = pwd
        self.conn = None
        self.wt_fname = list()
        self.wt_dname = list()
        self.wt_uname = list()

    def open(self) -> bool:
        rst: bool = False
        if self.conn is None:
            warnings.filterwarnings("ignore")
            cnopts = pysftp.CnOpts()
            cnopts.hostkeys = None
            self.conn = pysftp.Connection(host=self.host, port=self.port, username=self.usr, password=self.pwd, cnopts=cnopts)
            rst = True
        return rst

    def listdir(self, remotepath = ".") -> str:
        return self.conn.listdir(remotepath)

    def cd(self, remotepath = ".") -> str:
        return self.conn.chdir(remotepath)

    def getcwd(self) -> str:
        return self.conn.getcwd()

    def walktree(self, remotepath = ".") -> tuple:
        self.wt_fname.clear()
        self.wt_dname.clear()
        self.wt_uname.clear()
        self.conn.walktree(remotepath, self.__walktree_fcb, self.__walktree_dcb, self.__walktree_ucb)
        rst: tuple = (self.wt_fname, self.wt_dname, self.wt_uname)
        return rst

    def __walktree_fcb(self, fname) -> None:
        self.wt_fname.append(fname)

    def __walktree_dcb(self, dname) -> None:
        self.wt_dname.append(dname)

    def __walktree_ucb(self, uname) -> None:
        self.wt_uname.append(uname)

    def exists(self, remotepath = ".") -> bool:
        return self.conn.exists(remotepath)

    def makedirs(self, remotepath = ".") -> bool:
        return self.conn.makedirs(remotepath)

    def put_r(self, localpath = None, remotepath = None) -> bool:
        rst: bool = False
        try:
            self.conn.put_r(localpath, remotepath)
            rst = True
        except Exception as e:
            logging.debug("error occurred; localpath = %s, remotepath = %s, e = %s" % (localpath, remotepath, e))
        return rst

    def rmdir_r(self, remotepath = ".", recurred = False) -> bool:
        rst: bool = False
        logging.debug("remotepath = %s, recurred = %s" % (remotepath, repr(recurred)))
        try:
            for entry in self.conn.listdir_attr(remotepath):
                path: str = os.path.join(remotepath, entry.filename)
                if self.conn.isfile(path):
                    self.conn.remove(path)
                elif self.conn.isdir(path):
                    self.rmdir_r(path, True)
                else:
                    pass
            self.conn.rmdir(remotepath)
            rst = True
        except Exception as e:
            logging.debug("error occurred; remotepath = %s, e = %s" % (remotepath, e))
        return rst

    def get_r(self, remotepath = ".", localpath = ".") -> bool:
        return self.conn.get_r(remotepath, localpath)

    def close(self) -> bool:
        rst: bool = False
        if self.conn is not None:
            self.conn.close()
            rst = True
        return rst

class ArtifactCrawler(FtpCrawler):
    def __init__(self, host: str = None, port: int = None, usr: str = None, pwd: str = None) -> None:
        super().__init__(host, port, usr, pwd)

    def get_all(self, dir: str = "") -> list:
        named_dir: list = None
        if dir is not None:
            self.open()

            arl: list = dir.split(self.DIR_SEP)
            logging.debug(repr(arl))

            dir_last: str = None
            path_found: bool = True
            for i in range(len(arl)):
                cwdl: list = self.listdir()
                logging.debug("cwdl: %s %s" % (cwdl, type(cwdl)))
                logging.debug(arl[i])
                if arl[i] in cwdl:
                    dir_last = arl[i]
                    self.cd(arl[i])
                else:
                    path_found = False
            logging.debug("dir_last = %s" % (dir_last))
            logging.debug("path_found = %s" % (str(path_found)))

            if path_found is True:
                logging.debug("%s is existing" % (dir))
                cwd = self.getcwd()
                logging.debug("cwd = %s" % (cwd))
                (fnames, dnames, unames) = self.walktree(cwd)
                logging.debug("fnames = %s, dnames = %s, unames = %s" % (repr(fnames), repr(dnames), repr(unames)))
                named_dir = dnames
            else:
                logging.debug("Not existing")
            self.close()
        return named_dir

    def get_prefixed(self, dir: str = "", prefix: str = "") -> list:
        dir_dt_prefixed: list = list()
        if dir is not None and\
            prefix is not None:
            named_dir: list = self.get_all(dir = dir)
            PREFIX: str = dir
            if not PREFIX.endswith(self.DIR_SEP):
                PREFIX = PREFIX + self.DIR_SEP
            if not PREFIX.startswith(self.DIR_SEP):
                PREFIX = self.DIR_SEP + PREFIX
            PREFIX += prefix
            logging.debug("PREFIX = %s" % (PREFIX))
            for d in named_dir:
                if d.startswith(PREFIX):
                    logging.debug(d)
                    DELI: str = "_"
                    tok: list = d.split(DELI)
                    dir_dt: str = tok[-3:]
                    dt: datetime = ArtifactCrawler.__get_dt(DELI.join(dir_dt))
                    if dt is not None:
                        dir_dt_prefixed.append(os.path.basename(d))
        logging.debug("dir_dt_prefixed = %s" % (repr(dir_dt_prefixed)))
        return dir_dt_prefixed

    def get_preferred(self, dir: str = "", prefix: str = "") -> str:
        dir_dt_latest: str = None
        if dir is not None and\
            prefix is not None:
            named_dir: list = self.get_all(dir = dir)
            PREFIX: str = dir
            if not PREFIX.endswith(self.DIR_SEP):
                PREFIX = PREFIX + self.DIR_SEP
            if not PREFIX.startswith(self.DIR_SEP):
                PREFIX = self.DIR_SEP + PREFIX
            PREFIX += prefix
            logging.debug("PREFIX = %s" % (PREFIX))
            dt_latest: datetime = datetime(1970, 1, 1, 0, 0, 0)
            for d in named_dir:
                if d.startswith(PREFIX):
                    logging.debug(d)
                    DELI: str = "_"
                    tok: list = d.split(DELI)
                    dir_dt: str = tok[-3:]
                    dt: datetime = ArtifactCrawler.__get_dt(DELI.join(dir_dt))
                    if dt is not None:
                        logging.debug("dt = %s" % (dt))
                        td: timedelta = dt - dt_latest
                        if td.total_seconds() > 0:
                            dt_latest = dt
                            dir_dt_latest = os.path.basename(d)
        logging.debug("dt_latest = %s" % (repr(dt_latest)))
        return dir_dt_latest

    def is_upgrade_needed(self, dir: str = "", prefix: str = "", compared: str = "") -> bool:
        rst: bool = False
        if dir is not None and\
            prefix is not None and\
            compared is not None and\
            compared.startswith(prefix):
            DELI: str = "_"
            tok_compared: list = compared.split(DELI)
            dir_dt_compared: str = tok_compared[-3:]
            dt_compared: datetime = ArtifactCrawler.__get_dt(DELI.join(dir_dt_compared))
            logging.debug("dt_compared = %s" % (repr(dt_compared)))
            if dt_compared is not None:
                preferred: str = self.get_preferred(dir, prefix)
                if preferred is None:
                    rst = True
                else:
                    tok_preferred: list = preferred.split(DELI)
                    dir_dt_preferred: str = tok_preferred[-3:]
                    dt_preferred: datetime = ArtifactCrawler.__get_dt(DELI.join(dir_dt_preferred))
                    logging.debug("dt_preferred = %s" % (repr(dt_preferred)))
                    td: timedelta = dt_compared - dt_preferred
                    logging.debug("td = %s" % (repr(td)))
                    if td.total_seconds() < 0:
                        rst = True
        logging.debug("rst = %s" % (rst))
        return rst

    def remove_specific(self, dir: str = "", prefix: str = "", suffix: str = None) -> bool:
        rst: bool = False
        if prefix == "" or suffix == None:
            return rst

        DELI: str = "_"
        individual: str = prefix + DELI + suffix

        if dir is not None:
            self.open()

            arl: list = dir.split(self.DIR_SEP)
            logging.debug(repr(arl))

            dir_last: str = None
            path_found: bool = True
            for i in range(len(arl)):
                cwdl: list = self.listdir()
                logging.debug("cwdl: %s %s" % (cwdl, type(cwdl)))
                logging.debug(arl[i])
                if arl[i] in cwdl:
                    dir_last = arl[i]
                    self.cd(arl[i])
                else:
                    path_found = False
            logging.debug("dir_last = %s" % (dir_last))
            logging.debug("path_found = %s" % (str(path_found)))

            if path_found is True:
                logging.debug("%s is existing" % (dir))
                cwd = self.getcwd()
                logging.debug("cwd = %s" % (cwd))
                existing: bool = self.exists(individual)
                if existing is True:
                    individual_full: str = dir
                    if not individual_full.endswith(self.DIR_SEP):
                        individual_full += self.DIR_SEP
                    individual_full += individual
                    logging.debug("individual_full = %s" % (individual_full))
                    self.rmdir_r(individual)
                    logging.debug("%s is removed" % (individual))
                else:
                    rst = True
            else:
                logging.debug("Not existing")
            self.close()
        return rst

    def download(self, dir: str = "", prefix: str = "", suffix: str = None, local: str = ".") -> bool:
        rst: bool = False
        if prefix == "" or suffix == None:
            return rst

        DELI: str = "_"
        individual: str = prefix + DELI + suffix

        if dir is not None:
            self.open()

            arl: list = dir.split(self.DIR_SEP)
            logging.debug(repr(arl))

            dir_last: str = None
            path_found: bool = True
            for i in range(len(arl)):
                cwdl: list = self.listdir()
                logging.debug("cwdl: %s %s" % (cwdl, type(cwdl)))
                logging.debug(arl[i])
                if arl[i] in cwdl:
                    dir_last = arl[i]
                    self.cd(arl[i])
                else:
                    path_found = False
            logging.debug("dir_last = %s" % (dir_last))
            logging.debug("path_found = %s" % (str(path_found)))

            if path_found is True:
                logging.debug("%s is existing" % (dir))
                cwd = self.getcwd()
                logging.debug("cwd = %s" % (cwd))
                existing: bool = self.exists(individual)
                if existing is True:
                    cwdl: list = self.listdir(individual)
                    if len(cwdl) > 0:
                        path: str = local
                        if path != ".":
                            os.makedirs(path, mode = 0o777, exist_ok = True)
                        self.get_r(individual, path)
                        rst = True
                    else:
                        logging.debug("Empty")
            else:
                logging.debug("Not existing")
            self.close()
        return rst

    def upload(self, dir: str = "", prefix: str = "", suffix: str = None, local: str = ".") -> bool:
        rst: bool = False
        if prefix == "" or suffix == None:
            return rst

        DELI: str = "_"
        individual: str = prefix + DELI + suffix

        if dir is not None:
            self.open()

            arl: list = dir.split(self.DIR_SEP)
            logging.debug(repr(arl))

            dir_last: str = None
            path_found: bool = True
            for i in range(len(arl)):
                cwdl: list = self.listdir()
                logging.debug("cwdl: %s %s" % (cwdl, type(cwdl)))
                logging.debug(arl[i])
                if arl[i] in cwdl:
                    dir_last = arl[i]
                    self.cd(arl[i])
                else:
                    path_found = False
            logging.debug("dir_last = %s" % (dir_last))
            logging.debug("path_found = %s" % (str(path_found)))

            if path_found is True:
                logging.debug("%s is existing" % (dir))
                path: str = local
                if not path.endswith(os.path.sep):
                    path += os.path.sep
                path += individual
                logging.debug("path = %s" % (path))
                if os.path.exists(path):
                    cwd = self.getcwd()
                    logging.debug("cwd = %s" % (cwd))
                    existing: bool = self.exists(individual)
                    if existing is False:
                        logging.debug("directory %s would be created" % (individual))
                        self.makedirs(individual)
                    self.put_r(path, individual)
                    rst = True
                else:
                    logging.debug("path %s is not existing" % (path))
            else:
                logging.debug("Not existing")
            self.close()
        return rst

    @classmethod
    def __get_dt(cls, ts: str = None) -> datetime:
        fmt: str = "%b-%d-%Y__%H-%M-%S"
        dt: datetime = None
        try:
            dt = datetime.strptime(ts, fmt)
        except:
            pass
        return dt

if __name__ == "__main__":
    my_parser = argparse.ArgumentParser(description="CLI argument parsing")
    my_parser.add_argument("-v",
        "--verbose",
        action="store_true",
        help="verbosity")
    my_parser.add_argument(
        "--sftp-host",
        metavar="sftp_host",
        default="sftp.wi-fi.org",
        type=str,
        help="SFTP host")
    my_parser.add_argument(
        "--sftp-port",
        metavar="sftp_port",
        default=int(22),
        type=int,
        help="SFTP port")
    my_parser.add_argument(
        "--sftp-usr",
        metavar="sftp_usr",
        default="",
        type=str,
        help="SFTP username")
    my_parser.add_argument(
        "--sftp-pwd",
        metavar="sftp_pwd",
        default="",
        type=str,
        help="SFTP password")
    my_parser.add_argument(
        "--sftp-dir-ar",
        metavar="sftp_dir_ar",
        default="",
        type=str,
        help="SFTP directory for artifact")
    my_parser.add_argument(
        "--sftp-dir-ar-prefix",
        metavar="sftp_dir_ar_prefix",
        default="",
        type=str,
        help="the prefix of SFTP directory for artifact")
    my_parser.add_argument(
        "--sftp-dir-ar-suffix",
        metavar="sftp_dir_ar_suffix",
        default=None,
        type=str,
        help="the suffix of SFTP directory for artifact; a datetime formatted by \"%%b-%%d-%%Y__%%H-%%M-%%S\"")
    #my_parser.add_argument(
    #    "--sftp-dir-ar-individual",
    #    metavar="sftp_dir_ar_individual",
    #    default=None,
    #    type=str,
    #    help="the individual of SFTP directory for artifact; i.e. prefix plus suffix with a underscore in middle")
    my_parser.add_argument("-y",
        "--category",
        metavar="category",
        default="view",
        choices=["view", "get", "check", "remove", "download", "upload", "obtain"],
        type=str,
        help="category/mode for artifact manipulation;\
        view to list all items with specified prefix,\
        get to retrieve the preferred one items with specified prefix,\
        check to determine whether local version is update-to-date or not,\
        remove to delete the remote directory,\
        download to pull the specified directory from site,\
        upload to push the specified directory to site,\
        obtain to acquire a name for further uploading.\
        ")

    args = my_parser.parse_args()
    if args.verbose == True :
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.ERROR)
    logging.debug("args: " + repr(args))

    rst: int = 0
    if args.category == "view":
        ac: ArtifactCrawler = ArtifactCrawler(host = args.sftp_host, port = args.sftp_port, usr = args.sftp_usr, pwd = args.sftp_pwd)
        prefixed: list = ac.get_prefixed(dir = args.sftp_dir_ar, prefix = args.sftp_dir_ar_prefix)
        DELI: str = "\n"
        dumped: str = DELI.join(prefixed)
        print(dumped)
    elif args.category == "get":
        ac: ArtifactCrawler = ArtifactCrawler(host = args.sftp_host, port = args.sftp_port, usr = args.sftp_usr, pwd = args.sftp_pwd)
        preferred: str = ac.get_preferred(dir = args.sftp_dir_ar, prefix = args.sftp_dir_ar_prefix)
        print(preferred)
    elif args.category == "check":
        ar_dt: str = datetime.fromtimestamp(time.time()).strftime("%b-%d-%Y__%H-%M-%S")
        if args.sftp_dir_ar_suffix is not None:
            ar_dt = args.sftp_dir_ar_suffix
        dir_compared: str = args.sftp_dir_ar_prefix + ar_dt
        ac: ArtifactCrawler = ArtifactCrawler(host = args.sftp_host, port = args.sftp_port, usr = args.sftp_usr, pwd = args.sftp_pwd)
        is_needed: bool = ac.is_upgrade_needed(dir = args.sftp_dir_ar, prefix = args.sftp_dir_ar_prefix, compared = dir_compared)
        rst = 0 if is_needed is False else 1
    elif args.category == "remove":
        ac: ArtifactCrawler = ArtifactCrawler(host = args.sftp_host, port = args.sftp_port, usr = args.sftp_usr, pwd = args.sftp_pwd)
        removed: bool = ac.remove_specific(dir = args.sftp_dir_ar, prefix = args.sftp_dir_ar_prefix, suffix = args.sftp_dir_ar_suffix)
        rst = 0 if removed is True else 1
    elif args.category == "download":
        ac: ArtifactCrawler = ArtifactCrawler(host = args.sftp_host, port = args.sftp_port, usr = args.sftp_usr, pwd = args.sftp_pwd)
        downloaded: bool = ac.download(dir = args.sftp_dir_ar, prefix = args.sftp_dir_ar_prefix, suffix = args.sftp_dir_ar_suffix)
        logging.debug("downloaded = %s" % (repr(downloaded)))
        rst = 0 if downloaded is True else 1
    elif args.category == "upload":
        ac: ArtifactCrawler = ArtifactCrawler(host = args.sftp_host, port = args.sftp_port, usr = args.sftp_usr, pwd = args.sftp_pwd)
        uploaded: bool = ac.upload(dir = args.sftp_dir_ar, prefix = args.sftp_dir_ar_prefix, suffix = args.sftp_dir_ar_suffix)
        logging.debug("uploaded = %s" % (repr(uploaded)))
        rst = 0 if uploaded is True else 1
    elif args.category == "obtain":
        ar_dt: str = datetime.fromtimestamp(time.time()).strftime("%b-%d-%Y__%H-%M-%S")
        dir_obtaining: str = args.sftp_dir_ar_prefix + ar_dt
        print(dir_obtaining)
    else:
        pass

    exit(rst)

#Crawler6 - by Leo Liu
