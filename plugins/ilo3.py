import subprocess
import json

def run(host, port, definition, response):
    url = 'https://{host}:{port}/json/login_session'.format(host=host, port=443)
    # using curl because requests.get barfs with a SSLError (sslv3 alert handshake failure)
    try:
	r = subprocess.check_output(['curl', '--silent', '-k', url], stderr=None);
        jsond = json.loads(r)
        if jsond:
            definition[u'meta'][u'class'] = 'iLO 3'
            definition[u'meta'][u'ilo-version'] = jsond["version"]
    except (Exception) as e:
        # print('{url} request error: {ename} {eargs!r}'.format(url=url, ename=type(e).__name__, eargs=e.args))
        pass

    return definition
