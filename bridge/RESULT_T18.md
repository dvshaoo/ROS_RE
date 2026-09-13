# RESULT_T18: Server-List Subsystem Driver Map (Static RE)

## 1. Executive Summary
- **Subsystem Driver Chain**:
  `extconfigs.py:80-87` (`SERVER_LIST = '/server_list_ad.txt'`)
  → `ui/UILogin.py:130-136` (`UILogin.requestServerList`: `self.wc.fetch(extconfigs.SERVER_LIST)`)
  → `ui/UILogin.py:147-148` (`UILogin.initServerInfo`: receives plain text)
  → `ui/UILogin.py:151-177` (`UILogin.updateServerList`: `.split('\n')`)
  → `ui/UILogin.py:180-257` (`UILogin.parseOneServerInfo`: `.split(' ')`)
  → Decoded Model: `oneServerInfo` dict (`zone`, `numberSt`, `serverSt`, `name`, `tel`, `cnc`, `edu`, `net`, `groupid`, `udpIP`, `udpPort`, `ip`, `port`)
  → Client State: `self.saServerList` on `UILogin` instance → `ui/UILogin.py:1218` (`initServerList` latency tests) → `ui/UIServerList.py` (`serverInfoList` UI) → `UILogin.doLoginGame` / `startLogin` connection target (`serverInfo['ip']`, `serverInfo['port']`).

---

## 2. Dex References (AGENT.md T05)

File: `02_dex/classes.dex`
- **Offset `0x19c074`**: String `'ServerListURL'` in UniSDK config/protocol keys.
- **Offset `0x1f7e52`**: JNI methods `ntSetServerListURL` and `ntSetServerListURLwithNative` in `com.netease.unisdk.NativeInterface`.
- **Offset `0x1d6bd1`**: Method references `getServerList` and `getServerlisturl` in `com.netease.unisdk.serverlist.ServerListManager`.

---

## 3. Bytecode Request Builder & Dispatch

### Module: `extconfigs.py:80-87`
Determines which server list file to query based on platform:
```python
83: if platform == game3d.PLATFORM_IOS:
84:     SERVER_LIST = '/server_list_ios.txt'
85: elif isMuMuEmulator():
86:     SERVER_LIST = '/server_list_mumu.txt'
87: elif platform == game3d.PLATFORM_WIN32:
88:     SERVER_LIST = '/server_list_pc.txt'
    else: # Android
        SERVER_LIST = '/server_list_ad.txt'
```

### Module: `ui/UILogin.py:130-146` (`requestServerList`)
```python
130: def requestServerList(self):
131:     t0 = time.time()
132:     res = self.wc.fetch(extconfigs.SERVER_LIST)
133:     t_cost = int((time.time() - t0) * 1000)
134:     if res:
135:         DCTool.startDCTool(DCTool.DOWNLOAD_SERVER_LIST_SUC, time_cost=t_cost)
136:         self.initServerInfo(''.join(res))
137:     else:
138:         url = UILogin.domain + extconfigs.SERVER_LIST
139:         DCTool.startDCTool(DCTool.DOWNLOAD_SERVER_LIST_FAL, url=url, time_cost=t_cost)
140:         self.exceptionHandle(...)
```

---

## 4. Response Parser & Format (Static Truth: Plain Text, NOT JSON / Protobuf)

### Module: `ui/UILogin.py:151-177` (`updateServerList`)
The server list response is line-separated ASCII text (`\n`):
```python
151: def updateServerList(self, content):
153:     totalServer = content.split('\n')
155:     playerNetType = None
157:     saServerList = {}
158:     for serverInfo in totalServer:
159:         (zone, info) = self.parseOneServerInfo(serverInfo, playerNetType)
161:         if zone is not None and zone != 'Network':
162:             if zone not in saServerList:
163:                 saServerList[zone] = [info]
164:             else:
165:                 saServerList[zone].append(info)
166:         elif zone == 'Network':
167:             playerNetType = info
169:     self.saServerList = saServerList
172:     for zone, serverList in saServerList.iteritems():
173:         for server in serverList:
174:             ipAndPort = server.get('tel')
175:             (ip, port) = ipAndPort.split(':')
176:             server['ip'] = ip
177:             server['port'] = port
```

### Module: `ui/UILogin.py:180-257` (`parseOneServerInfo`)
Each line is space-separated (`.split(' ')`). Tokens are positional:
```python
197: server = serverInfo.strip().split(' ')
198: if serverInfo.find('#network') != -1:
         # network directive
201: if len(serverInfo.strip()) == 0 or len(server) < 9:
202:     return (None, None)
211: for i in xrange(1, 4):
212:     if not server[i].isdigit():
213:         return (None, None)
216: zone = server[0]
217: numberSt = int(server[1])
218: netSt = int(server[2])
219: serverSt = int(server[3])
220: name = getServerName(server[4], Globals.language)
221: oriName = server[5]
222: telIP = server[6]
223: cncIP = server[7]
224: eduIP = server[8].strip()
226: groupId = '10001'
227: if len(server) > 9 and server[9].isdigit():
228:     groupId = server[9]
231: udpIP = None; udpPort = None
234: if len(server) > 10:
235:     udpTest = server[10]
236:     (udpIP, udpPort) = udpTest.split(':')
237:     udpPort = int(udpPort)
244: oneServerInfo = {
         'zone': zone, 'numberSt': numberSt, 'serverSt': serverSt,
         'name': name, 'oriName': oriName, 'tel': telIP, 'cnc': cncIP,
         'edu': eduIP, 'net': netSt, 'groupid': groupId,
         'udpIP': udpIP, 'udpPort': udpPort
     }
257: return (zone, oneServerInfo)
```

---

## 5. Exact Serveable Schema for `server_list_ad.txt`

### Positional Column Specifications
Columns are separated by single ASCII spaces:
1. `zone` (`str`): Zone key / name without internal spaces (e.g. `North_America`).
2. `numberSt` (`int`): Display order / server index (e.g. `1`).
3. `netSt` (`int`): Network status flag (e.g. `1`).
4. `serverSt` (`int`): Server state (e.g. `1` = smooth / green, `2` = busy, `3` = full).
5. `name` (`str`): Server display name or translation ID (e.g. `US_Server`).
6. `oriName` (`str`): Original server name (e.g. `US_Server`).
7. `telIP` (`str`): Telecom address `host:port` (e.g. `127.0.0.1:25000`).
8. `cncIP` (`str`): Unicom address `host:port` (e.g. `127.0.0.1:25000`).
9. `eduIP` (`str`): Education network address `host:port` (e.g. `127.0.0.1:25000`).
10. `groupId` (`int`, optional): Server group ID (e.g. `10001`).
11. `udpTest` (`str`, optional): UDP latency test endpoint `host:port` (e.g. `127.0.0.1:25000`).

### Exact 1-Line Serveable Payload
```text
North_America 1 1 1 North_America North_America 127.0.0.1:25000 127.0.0.1:25000 127.0.0.1:25000 10001 127.0.0.1:25000
```
