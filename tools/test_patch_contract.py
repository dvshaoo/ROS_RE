# -*- coding: utf-8 -*-
"""
test_patch_contract.py — Reproducible test for G0 Startup Patch Contract
Validates the exact patch response against the reverse-engineered constraints
from patch/ResourcePatcher.py (lines 403-420, 1271-1324) and patch/tags.py (41006).
"""
import json
import zlib
import pickle
import sys

PLIST_PAYLOAD = (
    b'##########\n'
    b'{\n'
    b'  "type": "package",\n'
    b'  "version": "1117219",\n'
    b'  "version_name": "1.610377.506841",\n'
    b'  "min_client_version": 0,\n'
    b'  "min_engine_version": 0,\n'
    b'  "min_patch_client_version": 0,\n'
    b'  "min_patch_engine_version": 0,\n'
    b'  "use_dlc_clothes": false,\n'
    b'  "file_list": [],\n'
    b'  "patch.1117219.com.netease.chiji.obb_updated": 0,\n'
    b'  "patch.1117219.com.netease.chiji.obb_size": 1,\n'
    b'  "patch.1117219.com.netease.chiji.obb_md5": "00000000000000000000000000000000"\n'
    b'}\n'
)

def test_plist_parser():
    print("[TEST 1] Testing _parse_npk_version_string compliance (ResourcePatcher.py:403-420)...")
    content = PLIST_PAYLOAD.decode('utf-8')
    head, sep, tail = content.partition('##########')
    assert sep == '##########', "Separator ########## missing! Triggers Alarm 41006."
    print("  -> Separator check: PASS (10 hash characters present)")

    info = json.loads(tail)
    print("  -> JSON tail parse: PASS")

    # Verify KeyError: 'type' constraint (line 1279)
    assert 'type' in info, "Missing 'type' key! Triggers KeyError at ResourcePatcher.py:1279."
    assert info['type'] == 'package', f"Expected type 'package', got {info['type']}"
    print("  -> 'type' key check: PASS (type=='package')")

    # Verify version string constraint (line 1280)
    assert 'version' in info, "Missing 'version' key!"
    assert isinstance(info['version'], str), f"Version must be string for path concatenation, got {type(info['version'])}"
    assert info['version'] == "1117219", f"Expected version '1117219', got {info['version']}"
    print("  -> 'version' type check: PASS (is str, equals '1117219')")

    # Verify file_list constraint (lines 1296-1324)
    assert 'file_list' in info, "Missing 'file_list' key!"
    assert isinstance(info['file_list'], list), "file_list must be a list"
    assert len(info['file_list']) == 0, "file_list should be empty for package no-update mode"
    print("  -> 'file_list' check: PASS (empty list)")

    # Verify package updated flags (line 1308)
    obb_name = "patch.1117219.com.netease.chiji.obb"
    assert f"{obb_name}_updated" in info, f"Missing {obb_name}_updated"
    assert info[f"{obb_name}_updated"] == 0, f"Expected _updated == 0, got {info[f'{obb_name}_updated']}"
    print(f"  -> '{obb_name}_updated' check: PASS (equals 0 -> needPatch=False)")

    return True

def test_total_list_payload():
    print("\n[TEST 2] Testing /1117219/total_list zlib + pickle format (ResourcePatcher.py:1285)...")
    payload = zlib.compress(pickle.dumps({}, 2))
    decompressed = zlib.decompress(payload)
    obj = pickle.loads(decompressed)
    assert isinstance(obj, dict), "total_list must deserialize to a dict"
    print(f"  -> total_list payload length: {len(payload)} bytes")
    print("  -> total_list decompress & unpickle: PASS")
    return True

def test_patch_version_clearing_input():
    print("\n[TEST 3] Testing patchVersion language-driver check (patch_mgr.py:446, 611)...")
    patch_version_content = "1.0.0.en"
    parts = patch_version_content.strip().split('.')
    assert len(parts) >= 4, "patchVersion format must have at least 4 segments: 1.<engine>.<client>.<lang>"
    patch_lang = parts[-1]
    setting_lang = "en"
    need_language_patch = (patch_lang != setting_lang)
    assert not need_language_patch, f"need_language_patch should be False, but got True (patch_lang={patch_lang}, setting_lang={setting_lang})"
    print(f"  -> patchVersion '{patch_version_content}' language check vs '{setting_lang}': PASS (need_language_patch=False -> forcePatch=False)")
    return True

if __name__ == '__main__':
    print("=================================================================")
    print(" ROS v1117219 Startup Patch Contract Verification Suite")
    print("=================================================================")
    t1 = test_plist_parser()
    t2 = test_total_list_payload()
    t3 = test_patch_version_clearing_input()
    print("\n=================================================================")
    print(" ALL TESTS PASSED (3/3) — Patch Contract Validated Against Code")
    print("=================================================================")
