# Slice Plugins: For parsing VirtualInterfaces, VirtualBridges, and RadioInterfaces
# SAVI Mcgill: Heming Wen, Prabhat Tiwary, Kevin Han, Michael Smith
import copy
import importlib
import json
import os
import sys


class SlicePlugin(object):
    
    def __init__(self, tenant_id, user_id, tag=None):
        #To add later: RadioInterfaces
        self.plugins = {'VirtualInterfaces':'plugins.vif_plugin.VirtualInterfacePlugin',
                        'VirtualBridges':'plugins.vbr_plugin.VirtualBridgePlugin'}
        
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.tag = None
        if tag:
            self.tag = tag
        
    def parse_create_slice(self, data, numSlice, json_list):
        #Loop through values in plugin
        for key in self.plugins:
            if key in data:
                #Load the module
                module_name, class_name = self.plugins[key].rsplit(".",1)
                newmodule = importlib.import_module(module_name) #If module is already loaded, importlib will not load it again (already implemented in importlib)
                for i in range(numSlice): #loop through slice configs
                    try:
                        json_list[i][key] = getattr(newmodule, class_name)(self.tenant_id).parse(data[key], numSlice, i) #i is the current index
                    except Exception as e:
                        raise Exception(e.message)
            else: #Make default
                print(key+' not found. File might not parse correctly. Please check configuration and try again!')
                
        #Add wrapper around json_list and return
        return self._add_create_slice_wrapper(json_list, self.tag, self.user_id)
                
    def _add_create_slice_wrapper(self, json_list, tag, user_id):
        """This method takes a json_list and puts each entry in the correct format (i.e. user, slice, command, config)
        for sending to the APs"""
        newlist = []
        for entry in json_list:
            tempdata = {}
            tempdata['config'] = entry
            tempdata['user'] = user_id
            tempdata['slice'] = tag
            tempdata['command'] = 'create_slice'
            newlist.append(tempdata)     
        return newlist