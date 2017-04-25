# Copyright 2017 Battelle Energy Alliance, LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
'''
Created on April 4, 2017
@created: sonatsen (INL)
'''

from __future__ import division, print_function, unicode_literals, absolute_import
import warnings
warnings.simplefilter('default',DeprecationWarning)

from GenericCodeInterface import GenericCode
import os
import csv
from matplotlib.mlab import csv2rec

class Origen(GenericCode):
  def _readMoreXML(self,xmlNode):
    """
      Function to read the portion of the xml input that belongs to this specialized class and initialize
      some members based on inputs. This can be overloaded in specialize code interface in order to
      read specific flags
      @ In, xmlNode, xml.etree.ElementTree.Element, Xml element node
      @ Out, None.
    """
    self.origenOutputTables=[] #list of ORIGEN output variables of interest
    self.origenCaseNames=[] #list of ORIGEN output variables of interest
    
    GenericCode._readMoreXML(self,xmlNode)
    for child in xmlNode:
      if child.tag == 'OrigenOutputTables':
        #here the ORIGEN output variable that are off interest stored
        if child.text != None:
          self.origenOutputTables = child.text.split(',')
      if child.tag == 'OrigenCaseNames':
        #here the ORIGEN Case Names that are off interest stored
        if child.text != None:
          self.origenCaseNames = child.text.split(',')
    if (len(self.origenOutputTables)==0):
      warnings.warn('No ORIGEN Output table is selected by <OrigenOutputTables> node..."watts" is selected by default')
      self.origenOutputTables = ['watts']
    if (len(self.origenCaseNames)==0):
      warnings.warn('No ORIGEN Case Name is selected by <OrigenCaseNames> node...All will be included in the results')
      self.origenCaseNames = ['all']

  def finalizeCodeOutput(self, command, output, workingDir):
    """
      finalizeCodeOutput checks ORIGEN output files and looks for tables
      specified in <OrigenOutputTables> sections of raven input file. 
      @ In, command, string, the command used to run the just ended job
      @ In, output, string, the Output name root
      @ In, workingDir, string, current working dir
      @ Out, output, string, output csv file containing the tables of interest specified in the input
    """
    keywordDictionary = {}
    # open the original ORIGEN output file for reading
    fileobject = open(os.path.join(workingDir,output.split("out~")[1])  + '.out', 'r')
    # create the csv file for writing
    outputCSVfile = open (os.path.join(workingDir,output) + '.csv','w+') # store all the lines into a list
    lines = fileobject.readlines()
    for line in lines:
      listSplitted = [l.strip("'") for l in line.split()]
      for keyword in self.origenCaseNames:
        for case in listSplitted:
          if keyword == case:
            if not keywordDictionary.has_key(case):
              keywordDictionary[case] = {}
            for tables in self.origenOutputTables:
              if listSplitted[listSplitted.index(keyword)-3] == tables:
                newLineTime = lines[lines.index(line)+5]   
                keywordDictionary[case]['time'] = [s.strip('y').strip('d') for s in newLineTime.split()]
                if not keywordDictionary[case].has_key(tables):
                  keywordDictionary[case][tables] = {}
                i = 1
                while (newLineTime[0] != '='):
                  newLineTime = lines[lines.index(line)+5+i]   
                  if (newLineTime[0] != '-') and ((newLineTime[0] != '=')):
                    temp = newLineTime.split()
                    keywordDictionary[case][tables][temp[0]] = []
                    for j in temp[1:]:
                      try:
                        keywordDictionary[case][tables][temp[0]].append(float(j))
                      except ValueError:
                        keywordDictionary[case][tables][temp[0]].append(float(0))                  
                  i = i + 1
    for case in keywordDictionary.keys():
      for table in keywordDictionary[case].keys():
        if (table != 'time'):          
          for key in keywordDictionary[case][table].keys():
            outputCSVfile.write(str(case)+'_'+str(table)+'_'+str(key)+',')
        else:
          if (case != keywordDictionary.keys()[-1]):
            outputCSVfile.write(str(case)+'_'+str('time')+',')
          else:
            outputCSVfile.write(str(case)+'_'+str('time'))
    outputCSVfile.write('\n')
    for i in range(len(keywordDictionary[case]['time'])):
      for case in keywordDictionary.keys():
        for table in keywordDictionary[case].keys():
          if (table != 'time'):          
            for key in keywordDictionary[case][table].keys():
              outputCSVfile.write(str(keywordDictionary[case][table][key][i])+',')
          else:
            if (case != keywordDictionary.keys()[-1]):
              outputCSVfile.write(str(keywordDictionary[case][table][i])+',')
            else:
              outputCSVfile.write(str(keywordDictionary[case][table][i]))
      outputCSVfile.write('\n')
    outputCSVfile.close()