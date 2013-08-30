# VirtualInterfaces plugin for slice_plugin
# SAVI Mcgill: Heming Wen, Prabhat Tiwary, Kevin Han, Michael Smith

import json, os, copy, importlib, sys

class VirtualInterfaceManager():

    def __init__(self, tenant_id):
        self.tenant_id = tenant_id
        self.flavors = {'capsulator':'plugins.CapsulatorPlugin.CapsulatorPlugin', 'veth':'plugins.VethPlugin.VethPlugin'}
        self.default = [{'flavor':'veth', 'attributes':{"attach_to":"wlan0", "name":"vwlan0"}}]
        
    def parse(self, data, numSlice, currentIndex):
        VInt = [[] for x in range(len(data))] #Initialize list to data length
        if len(data) == 0: #Return basic default
            return self.default
            
        else:
            #Loop through VirtualInterfaces
            for (index, entry) in enumerate(data):
                if entry['flavor'] not in self.flavors:
                    print('Error! Unknown Flavor in VirtualInterfaces!')
                    sys.exit(-1)
                else:
                    #Load the module
                    module_name, class_name = self.flavors[entry['flavor']].rsplit(".",1)
                    newmodule = importlib.import_module(module_name) #If module is already loaded, importlib will not load it again (already implemented in importlib)
                    VInt[index] = getattr(newmodule, class_name)(self.tenant_id).parse(entry, numSlice, currentIndex, index) #Last index represents the VInt entry number
        
        return VInt