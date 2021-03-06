#!/usr/bin/env python
"""
httpscan

Scan networks for HTTP servers
"""
import argparse
import imp
import json
import re
import string
import warnings
from copy import deepcopy
from glob import glob
from os.path import basename, exists
from sys import exit

import requests

from scanner import scan
from logger import log

# To avoid "RuntimeWarning: Parent module 'plugins' not found while handling
# absolute import"
warnings.filterwarnings("ignore")

PORT = 80


#
# Main
#
if __name__ == '__main__':
    ###########################################################################
    # Bootstrap
    #

    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Scan networks for HTTP servers')
    parser.add_argument('hosts', help='An IP address for a hostname or network, example: 192.168.1.1 for single host or 192.168.1.1-254 for network.')
    parser.add_argument('--fast', help='Change timeout settings for the scanner in order to scan faster (T5).', default=False, action='store_true')
    parser.add_argument('--definitions-create', help='Create a definition for a given host', default=False, action='store_true')
    parser.add_argument('--port', help='Port to be scanned (default: 80)', type=str, default=PORT)
    parser.add_argument('--allow-redirects', dest='allow_redirects', action='store_true')
    parser.add_argument('--no-allow-redirects', dest='allow_redirects', action='store_false')
    parser.set_defaults(allow_redirects=True)
    parser.add_argument('--debug', help='Show additionalinformation in the logs', action='store_true', default=False)
    args = parser.parse_args()

    # Set debug mode if --debug
    if args.debug:
        log.level = 10

    ###########################################################################
    # Create new definition from host if "--definitions-create" argument is set
    #
    if args.definitions_create:
        url = 'http://{host}:{port}/'.format(host=args.hosts, port=args.port)
        try:
            response = requests.get(url, timeout=5, verify=False, allow_redirects=args.allow_redirects)
        except (requests.exceptions.RequestException, requests.exceptions.SSLError) as e:
            log.debug('{url} request error: {ename} {eargs!r}'.format(url=url, ename=type(e).__name__, eargs=e.args))
            exit()

        valid_charcters = string.ascii_lowercase + string.digits
        name = ''.join([char for char in response.headers.get('server', '').lower() if char in valid_charcters])
        if not name:
            log.debug('Unable to find proper information to create a definition of {url}'.format(url=url))
            exit()
        definition_path = 'definitions/{}.json'.format(name)
        template = json.loads(open('definitions/template.json', 'r').read())
        template['name'] = name
        template['rules']['headers']['server'] = [response.headers.get('server')]
        if exists(definition_path):
            log.warning('Definition {name} already exists'.format(name=name))
            exit()
        # Save definition
        f = file(definition_path, 'w')
        f.write(json.dumps(template, indent=4))
        print template
        exit()


    ###########################################################################
    # Scan
    #
    log.debug('Scanning...')
    hosts = scan(args.hosts, args.port, args.fast)
    if not hosts:
        log.debug('No hosts found with port {port} open.'.format(port=args.port))
        exit()

    ###########################################################################
    # Fingerprint
    #

    # Load definitions DB
    definitions_db = {}
    for definition_path in glob('definitions/*.json'):
        try:
            definitions_db[basename(definition_path[:-5])] = json.loads(
                open(definition_path).read()
            )
        except ValueError:
            log.warning(
                'Unable to load "{path}" due to malformed JSON'.format(
                    path=definition_path
                )
            )

    # Compile regexp
    regexp_header_server = []
    for name, definition in definitions_db.iteritems():
        for r in definition.get('rules').get('headers').get('server'):
            regexp_header_server.append((re.compile(r), name))
    regexp_body = []
    for name, definition in definitions_db.iteritems():
        if definition.get('rules').get('body'):
            for r in definition.get('rules').get('body'):
                regexp_body.append((re.compile(r), name))

    for host, port in hosts:
        # Make HTTP request
        url = 'http://{host}:{port}/'.format(host=host, port=port)
        try:
            response = requests.get(url, timeout=5, verify=False, allow_redirects=args.allow_redirects)
        except (requests.exceptions.RequestException, requests.exceptions.SSLError) as e:
            log.debug('{url} request error: {ename} {eargs!r}'.format(url=url, ename=type(e).__name__, eargs=e.args))
            continue

        identity = None

        #
        # Analyze response
        #

        # HTTP server header
        header_server = response.headers.get('server')
        if header_server:
            for regexp, http_server in regexp_header_server:
                if regexp.search(header_server):
                    identity = definitions_db.get(http_server)
                    break

        # Body
        body = response.text
        if body and not identity:
            for regexp, http_server in regexp_body:
                if regexp.search(body):
                    identity = definitions_db.get(http_server)
                    break

        # If identity found, search and run plugins. Default identity otherwise.
        if identity:
            if identity.get('plugins') and isinstance(identity.get('plugins'), list):
                for plugin_name in identity.get('plugins'):
                    try:
                        plugin_information = imp.find_module(plugin_name, ['plugins'])
                        if plugin_information:
                            plugin = imp.load_module(
                                'plugins.{name}'.format(name=plugin_name),
                                *plugin_information
                            )
                            identity = plugin.run(host, args.port, deepcopy(identity), response)
                    except (ImportError, Exception) as e:
                        log.warning(
                            'Unable to load plugin "{}" for "{}" definition: {}'.format(
                                plugin_name, identity.get('name'), e
                            )
                        )
        else:
            identity = {'name': header_server}

        log.info('http://{host}:{port}/ {definition_name} | {definition_meta}'.format(
            host=host,
            port=args.port,
            definition_name=identity.get('name'),
            definition_meta=identity.get('meta')
            )
        )
