#!/usr/bin/python -tt
# Aurora-client Shell
# 2014
# SAVI McGill: Heming Wen, Prabhat Tiwary, Kevin Han, Michael Smith,
#              Mike Kobierski and Hoai Phuoc Truong
#

"""
Command-line interface to the Aurora API
Uses a JSON file for commands
Format:[
         {
          optional:[[oarg1, {attributes}],[oarg2, {attributes}]...], 
          positional:[[parg1, {attributes}], [parg2, {attributes}]...], 
          subargument:[[subarg1, {attributes}, [[osarg1, {attributes}], [osarg2, {attributes}]]], [subarg2, {attributes}]...]
         }
       ]
"""

import argparse
import json
import os
from pprint import pprint
import sys
import traceback

#from keystoneclient.v2_0 import client as ksclient #commented in order to compile locally
import config
import utils
from auroraclient import json_sender
from auroraclient import slice_json_generator

CLIENT_DIR = os.path.dirname(os.path.abspath(__file__))
CLIEN_JSON_DIR =  os.path.join(CLIENT_DIR, 'json')

class AuroraArgumentParser(argparse.ArgumentParser):
    
    def base_parser(self):
        parser = argparse.ArgumentParser(prog='aurora', description='Virtualization and SDI for wireless access points (SAVI Testbed)',
                                         epilog='Created by the SAVI McGill Team')
        
        subparsers = parser.add_subparsers()
        
        # Load the JSON file
        try:
            with open(os.path.join(CLIEN_JSON_DIR, 'shell.json'), 'r') as JFILE:
                commands = json.load(JFILE)[0]
        except:
            print('Error loading json file!')
            sys.exit(-1)
        
        # Load all optional arguments
        for oarg in commands['optional']:
            parser.add_argument(oarg[0], action=oarg[1]['action'], nargs=oarg[1]['nargs'], default=oarg[1]['default'],
                                choices=oarg[1]['choices'], metavar=oarg[1]['metavar'], help=oarg[1]['help'])
                                
        
        # Load all positional arguments
        for parg in commands['positional']:
            parser.add_argument(parg[0], action=parg[1]['action'], nargs=parg[1]['nargs'], default=parg[1]['default'],
                                choices=parg[1]['choices'], metavar=parg[1]['metavar'], help=parg[1]['help'])
                                
       
        # Load all sub arguments
        for subarg in commands['subargument']:
            temp_parser = subparsers.add_parser(subarg[0], help=subarg[1]['help'])
            temp_parser.add_argument(subarg[0], action=subarg[1]['action'], nargs=subarg[1]['nargs'], default=subarg[1]['default'],
                                     choices=subarg[1]['choices'], metavar=subarg[1]['metavar'])
            
            # Load all optional and positional arguments for the current sub arguemnt
            for osarg in subarg[2]:
                if type(osarg[0]) is list and osarg[1]['action']=='store':
                    temp_parser.add_argument(*osarg[0], action=osarg[1]['action'], nargs=osarg[1]['nargs'], default=osarg[1]['default'],
                                             choices=osarg[1]['choices'], metavar=osarg[1]['metavar'], help=osarg[1]['help'], 
                                             required=osarg[1].get('required', False))
                
                elif type(osarg[0]) is not list and osarg[1]['action']=='store':
                    temp_parser.add_argument(osarg[0], action=osarg[1]['action'], nargs=osarg[1]['nargs'], default=osarg[1]['default'],
                                             choices=osarg[1]['choices'], metavar=osarg[1]['metavar'], help=osarg[1]['help'], 
                                             required=osarg[1].get('required', False))
                
                elif type(osarg[0]) is list and osarg[1]['action']=='store_true':
                    temp_parser.add_argument(*osarg[0], action=osarg[1]['action'], default=osarg[1]['default'], help=osarg[1]['help'], 
                                             required=osarg[1].get('required', False))
                                             
                else:
                    temp_parser.add_argument(osarg[0], action=osarg[1]['action'], default=osarg[1]['default'], help=osarg[1]['help'], 
                                             required=osarg[1].get('required', False))
            if len(subarg) == 4:
                # Positional subargs are present
                for psarg in subarg[3]:
                    if type(psarg[0]) is list and psarg[1]['action']=='store':
                        temp_parser.add_argument(*psarg[0], action=psarg[1]['action'], nargs=psarg[1]['nargs'], default=psarg[1]['default'],
                                                 choices=psarg[1]['choices'], metavar=psarg[1]['metavar'], help=psarg[1]['help'])
                    
                    elif type(psarg[0]) is not list and psarg[1]['action']=='store':
                        temp_parser.add_argument(psarg[0], action=psarg[1]['action'], nargs=psarg[1]['nargs'], default=psarg[1]['default'],
                                                 choices=psarg[1]['choices'], metavar=psarg[1]['metavar'], help=psarg[1]['help'])
                    
                    elif type(psarg[0]) is list and psarg[1]['action']=='store_true':
                        temp_parser.add_argument(*psarg[0], action=psarg[1]['action'], default=psarg[1]['default'], help=psarg[1]['help'])
                                                 
                    else:
                        temp_parser.add_argument(psarg[0], action=psarg[1]['action'], default=psarg[1]['default'], help=psarg[1]['help'])
        
        return parser

class AuroraConsole():

    def main(self, argv):
        if(len(argv) < 2):
            print('Error! Unexpected number of arguments.')
        else:
            function = argv[1] # Used for attrs function call
            manager_addr = config.CONFIG['connection']['manager_host']

            parser = AuroraArgumentParser()
            params = vars(parser.base_parser().parse_args(argv[1:]))

            #print 'function: %s' % function

            #For add-slice and modify, we need to load the JSON file
            if function == 'ap-slice-create':
                if not (params['file'] or params['hint']):                
                    print 'Please specify a file argument or hint!'
                    return
                elif params['file'] and not params['hint']:
                    try:
                        JFILE = open(os.path.join(CLIENT_DIR, 'json', params['file'][0]), 'r')
                        #print JFILE
                        file_content = json.load(JFILE)
                        params['file'] = file_content
                        JFILE.close()
                    except:
                        print('Error loading json file!')
                        sys.exit(-1)
            #Authenticate

#            try:
#                authInfo = self.authenticate()
#            except:
#                print 'Invalid Credentials!'
#                sys.exit(-1)       
            #if params.get('hint') is not None: #--"hint" token, store params['file'] for the third sent
             #   store = params['file'] 
             #   params['file']= None
                
            tenant_id = os.environ.get("AURORA_TENANT", config.CONFIG['tenant_info']['tenant_id'])
            project_id = os.environ.get("AURORA_PROJECT", config.CONFIG['tenant_info']['project_id'])
            user_id = os.environ.get("AURORA_USER", config.CONFIG['tenant_info']['user_id'])
            sending_address = 'http://' + config.CONFIG['connection']['manager_host'] + ':' + config.CONFIG['connection']['manager_port']
            #We will send in the following format: {function:"",parameters:""}
            msg = self._send_to_server(sending_address, function, params)

            try:
                arg_hint = params.get('hint')
                arg_ap = params.get('ap')

                if arg_hint is None:
                    sys.exit(0)
                if "location" in arg_hint or "location,slice-load" in arg_hint: # Once the token is 'hint', wait for users' reply
                    ap_locations = msg.get('ap_location')
                    if msg['ap_location'] == "": # in case of APs are full
                        print "Warning: No AP is currently available!!!"
                        sys.exit(0)

                    exitLoop = False
                    while not exitLoop:
                        if params.get('location') is None:
                            print ap_locations
                            print "Please Enter the location where the AP you want to access:"
                            print "(Enter 0 to leave otherwise)"

                            choice = raw_input()
                        else:
                            choice = params.get('location')[0]
                        if choice == '0':
                            exitLoop = True;
                        elif len(choice) > 0: # Unable to do a logic checking here due to the lack of data at the file
                            print "the location is " + choice
                            to_send = None
                            if params.get('location') is None:
                                ##############Send the information back again to the manager###############
                                params['location'] = [choice]
                                if arg_ap:
                                    params['favored_ap'] = arg_ap

                                request_id = utils.generate_request_id()
                                to_send = {
                                    'function':function,
                                    'parameters':params,
                                    'tenant_id': tenant_id,
                                    'project_id': project_id,
                                    'user_id': user_id,
                                    'request_id': request_id,
                                }
                            
                            if to_send:
                                message = json_sender.JSONSender().send_json(sending_address, to_send, request_id)
                            else:
                                message = msg

                            GEN_JSON_FNAME = 'gen_config.json'
                            GEN_JSON_FPATH = os.path.join(CLIEN_JSON_DIR, GEN_JSON_FNAME)

                            if message is not None: # Restore params['file'] and clean up params['hint'] to create a slice
                                if len(message['ap_location']) == 0: #There is no chosen ap
                                    print "Cannot locate an available AP based on provided information"
                                    break

                                params['hint'] = None
                                del params['location']
                                params['ap'] = [message['ap']]

                                if message['ssid'] is None:
                                    params['ssid'] = None
                                    ssid = None
                                    print "ssid is not provided or invalid"
                                else:
                                    ssid = params['ssid'][0]

                                if message['bridge']['flavor'] is None:
                                    bridge = None
                                    params['bridge'] = None
                                    print "bridge is not provided or invalid"
                                else:
                                    bridge = {}
                                    bridge['name'] = params['bridge'][0]

                                user_config = {
                                    'ap': params['ap'][0],
                                    'ssid': ssid,
                                    'bridge': bridge,
                                }

                                self.slice_json_generator = \
                                slice_json_generator.SliceJsonGenerator(
                                    user_config,
                                    GEN_JSON_FPATH,
                                    1, tenant_id, project_id
                                ) # Initialize the slice_json_generator

                                params['file'] = [GEN_JSON_FPATH,]

                                try:
                                    JFILE = open(os.path.join(CLIENT_DIR, 'json', params['file'][0]), 'r')
                                    #print JFILE
                                    file_content = json.load(JFILE)
                                    params['file'] = file_content
                                    JFILE.close()
                                except:
                                    print('Error loading json file!')
                                    sys.exit(-1)

                                message = self._send_to_server(sending_address, function, params)
                            exitLoop = True;
                        else:
                            exitLoop = True;
                            print "Invalid information"
            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                print "Finshed the current statement"
                    
            
    def _send_to_server(self, sending_address, function, params):
        tenant_id = os.environ.get("AURORA_TENANT", config.CONFIG['tenant_info']['tenant_id'])
        project_id = os.environ.get("AURORA_PROJECT", config.CONFIG['tenant_info']['project_id'])
        user_id = os.environ.get("AURORA_USER", config.CONFIG['tenant_info']['user_id'])

        request_id = utils.generate_request_id()
        ## print params
        to_send = {
            'function':function,
            'parameters':params,
            'tenant_id': tenant_id,
            'project_id': project_id,
            'user_id': user_id,
            'request_id': request_id
        }
        ##FOR DEBUGGING PURPOSES
        #pprint(to_send)
        ##END DEBUG
        
        if to_send:
            message = json_sender.JSONSender().send_json(sending_address, to_send, request_id) # change back to 132.206.206.133:5554
        return message
            
            
    def _get_ksclient(self, **kwargs):
        """Get an endpoint and auth token from Keystone.
        :param username: name of user
        :param password: user's password
        :param tenant_id: unique identifier of tenant
        :param tenant_name: name of tenant
        :param auth_url: endpoint to authenticate against
        """
        return ksclient.Client(username=kwargs.get('username'),
                               password=kwargs.get('password'),
                               tenant_id=kwargs.get('tenant_id'),
                               tenant_name=kwargs.get('tenant_name'),
                               auth_url=kwargs.get('auth_url'),
                               cacert=kwargs.get('cacert'),
                               insecure=kwargs.get('insecure'))
    
    def authenticate(self):
        kwargs = {
                    'username': os.getenv('OS_USERNAME'),
                    'password': os.getenv('OS_PASSWORD'),
                    'tenant_id': os.getenv('OS_TENANT_ID'),
                    'tenant_name': os.getenv('OS_TENANT_NAME'),
                    'auth_url': os.getenv('OS_AUTH_URL'),
                    'endpoint_type': os.getenv('OS_ENDPOINT_TYPE'),
                    'cacert': os.getenv('OS_CACERT'),
                    'insecure': False,
                    'region_name': os.getenv('OS_REGION_NAME')
                }
        _ksclient = self._get_ksclient(**kwargs)
        token = _ksclient.auth_token
        return token
        
def main():
    AuroraConsole().main(sys.argv)
        
if __name__ == '__main__':
    main()
