import requests
import json

def run(host, port, definition, response):
    url = 'https://{host}:{port}/rest/v1'.format(host=host, port=443)
    try:
        r = requests.get(url, timeout=5, verify=False, allow_redirects=False)
        if r.status_code == 200:
           jsond = json.loads(r.text)
           if jsond:
               definition[u'meta'][u'class'] = jsond["Oem"]["Hp"]["Manager"][0]["ManagerType"]
               definition[u'meta'][u'ilo-version'] = jsond["Oem"]["Hp"]["Manager"][0]["ManagerFirmwareVersion"]
    except (Exception) as e:
        # print('{url} request error: {ename} {eargs!r}'.format(url=url, ename=type(e).__name__, eargs=e.args))
        pass

    return definition
