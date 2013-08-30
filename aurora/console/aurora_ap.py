# Aurora AP/AP Slice Functions (Generates a Json File)
# SAVI Mcgill: Heming Wen, Prabhat Tiwary, Kevin Han, Michael Smith

import json
import sys

class AuroraAP():
    
    def __init__(self):
        self.slices = []
        try:
            self.JFILE = open('aplist.json', 'r')
            self.APlist = json.load(self.JFILE)
        except IOError:
            print('Error opening file!')
            sys.exit(-1)
    
    def ap_list(self, args="", info=False):
        if len(args) == 0: #No filter or tags
            for entry in self.APlist:
                print('\nName: '+entry[0])
                if info == True: #Print extra data
                    for attr in entry[1]:
                        print(attr+': '+entry[1][attr])
        elif len(args.split()) == 1: #Simple filter
            if '=' in args:
                if args.split('=')[0] == "location":
                    toPrint = filter(lambda x: (args.split('=')[1] in x[1][args.split['='][0]]), self.APlist)
                else:
                    toPrint = filter(lambda x: (x[1][args.split('=')[0]] == args.split('=')[1]), self.APlist)
            elif '!' in args:
                if args.split('!')[0] == "location":
                    toPrint = filter(lambda x: (args.split('!')[1] not in x[1][args.split['!'][0]]), self.APlist)
                else:
                    toPrint = filter(lambda x: (x[1][args.split('!')[0]] != args.split('!')[1]), self.APlist)
            elif '<' in args:
                toPrint = filter(lambda x: (float(x[1][args.split('<')[0]]) < float(args.split('<')[1])), self.APlist)
            elif '>' in args:
                toPrint = filter(lambda x: (float(x[1][args.split('>')[0]]) > float(args.split('>')[1])), self.APlist)
            else:
                print('Invalid command!')
                return
            for entry in toPrint:
                print('\nName: '+entry[0])
                if info == True: #Print extra data
                    for attr in entry[1]:
                        print(attr+': '+entry[1][attr])
        else: #parse the string (Format Example: "location=mcgill & firmware!2 & location=toronto")
            op = args.split()
            atom = op.pop(0)
            if '=' in atom:
                if atom.split('=')[0] == "location":
                    workinglist = filter(lambda x: (atom.split('=')[1] in x[1]['location']), self.APlist)
                else:
                    workinglist = filter(lambda x: (x[1][atom.split('=')[0]] == atom.split('=')[1]), self.APlist)
            elif '!' in atom:
                if atom.split('!')[0] == "location":
                    workinglist = filter(lambda x: (atom.split('!')[1] not in x[1][atom.split['!'][0]]), self.APlist)
                else:
                    workinglist = filter(lambda x: (x[1][atom.split('!')[0]] != atom.split('!')[1]), self.APlist)
            elif '<' in atom:
                workinglist = filter(lambda x: (float(x[1][atom.split('<')[0]]) < float(atom.split('<')[1])), self.APlist)
            elif '>' in atom:
                workinglist = filter(lambda x: (float(x[1][atom.split('>')[0]]) > float(atom.split('>')[1])), self.APlist)
            while len(op) > 0:
                if (len(op) % 2) != 0 or len(op[1]) == 1: #Incorrect amount of arguments
                    print('Insufficient number of arguments!')
                    return
                else:
                    atom = op.pop(1)
                    if '=' in atom:
                        if atom.split('=')[0] == "location":
                            templist = filter(lambda x: (atom.split('=')[1] in x[1]['location']), self.APlist)
                        else:
                            templist = filter(lambda x: (x[1][atom.split('=')[0]] == atom.split('=')[1]), self.APlist)
                    elif '!' in atom:
                        if atom.split('!')[0] == "location":
                            templist = filter(lambda x: (atom.split('!')[1] not in x[1]['location']), self.APlist)
                        else:
                            templist = filter(lambda x: (x[1][atom.split('!')[0]] != atom.split('!')[1]), self.APlist)
                    elif '<' in atom:
                        templist = filter(lambda x: (float(x[1][atom.split('<')[0]]) < float(atom.split('<')[1])), self.APlist)
                    elif '>' in atom:
                        templist = filter(lambda x: (float(x[1][atom.split('>')[0]]) > float(atom.split('>')[1])), self.APlist)
                    operation = op.pop(0)
                    if operation == "&":
                        workinglist = self.intersection(workinglist, templist)
                    else:
                        print('Unexpected character!')
                        return
            for entry in workinglist:
                print('\nName: '+entry[0])
                if info == True: #Print extra data
                    for attr in entry[1]:
                        print(attr+': '+entry[1][attr])
    
    def intersection(self, li1, li2): #for parsing and
        result = filter(lambda x: x in li1, li2)
        return result
    
    def ap_show(self, name):
        for entry in self.APlist:
            if entry[0] == name:
                print('\nName: '+entry[0])
                for attr in entry[1]:
                    print(attr+': '+entry[1][attr])
#Testing
#AuroraAP().ap_list("region=mcgill & number_radio=2 & version<1.1 & number_radio_free>0 & supported_protocol=a/b/g", True)
#AuroraAP().ap_show("OpenFlowKevin")
    