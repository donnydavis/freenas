#!/usr/bin/env python3.6

# Author: Eric Turgeon
# License: BSD
# Location for tests into REST API of FreeNAS

import unittest
import sys
import os
import xmlrunner
apifolder = os.getcwd()
sys.path.append(apifolder)
from functions import PUT, POST, GET_OUTPUT, DELETE, DELETE_ALL
from auto_config import results_xml

try:
    from config import BRIDGEHOST
except ImportError:
    RunTest = False
else:
    MOUNTPOINT = "/tmp/webdav-osx" + BRIDGEHOST
    RunTest = True
TestName = "update webdav osx"

DATASET = "webdavshare"
DATASET_PATH = "/mnt/tank/%s/" % DATASET
TMP_FILE = "/tmp/testfile.txt"
SHARE_NAME = "webdavshare"
SHARE_USER = "webdav"
SHARE_PASS = "davtest2"


class webdav_osx_test(unittest.TestCase):

    # Clean up any leftover items from previous failed test runs
    @classmethod
    def setUpClass(inst):
        payload1 = {"webdav_name": SHARE_NAME,
                    "webdav_comment": "Auto-created by ixbuild tests",
                    "webdav_path": DATASET_PATH}
        DELETE_ALL("/sharing/webdav/", payload1)
        PUT("/services/services/webdav/", {"srv_enable": False})
        DELETE("/storage/volume/1/datasets/%s/" % DATASET)

    def test_01_Creating_dataset_for_WebDAV_use(self):
        assert POST("/storage/volume/tank/datasets/", {"name": DATASET}) == 201

    def test_02_Changing_permissions_on_DATASET_PATH(self):
        payload = {"mp_path": DATASET_PATH,
                   "mp_acl": "unix",
                   "mp_mode": "777",
                   "mp_user": "root",
                   "mp_group": "wheel"}
        assert PUT("/storage/permission/", payload) == 201

    def test_03_Creating_WebDAV_share_on_DATASET_PATH(self):
        payload = {"webdav_name": SHARE_NAME,
                   "webdav_comment": "Auto-created by ixbuild tests",
                   "webdav_path": DATASET_PATH}
        assert POST("/sharing/webdav/", payload) == 201

    def test_04_Starting_WebDAV_service(self):
        assert PUT("/services/services/webdav/", {"srv_enable": True}) == 200

    def test_05_Changing_password_for_webdev(self):
        payload = {"webdav_password": SHARE_PASS}
        assert PUT("/services/services/webdav/", payload) == 200

    def test_06_Stopping_WebDAV_service(self):
        assert PUT("/services/services/webdav/", {"srv_enable": False}) == 200

    def test_07_Verifying_that_the_WebDAV_service_has_stopped(self):
        assert GET_OUTPUT("/services/services/webdav",
                          "srv_state") == "STOPPED"


def run_test():
    suite = unittest.TestLoader().loadTestsFromTestCase(webdav_osx_test)
    xmlrunner.XMLTestRunner(output=results_xml, verbosity=2).run(suite)

if RunTest is True:
    print('\n\nStarting %s tests...' % TestName)
    run_test()
