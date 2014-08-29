'''

Created on July 16, 2014

@author: alfoa

comments: Interface for 0-Dimensional fuel gas release HOBO

'''

from __future__ import division, print_function, unicode_literals, absolute_import
import warnings
warnings.simplefilter('default',DeprecationWarning)

import os
import copy
import shutil
import math

class HOBOInterface:
  '''this class is used a part of a code dictionary to specialize Model.Code for ExampleCode'''
  def generateCommand(self,inputFiles,executable,flags=None):
    '''seek which is which of the input files and generate According the running command'''
    # here the developer generates the command...
    # for this particular code, we have to retrieve the path of the executable contained into the generated input files
    # (remember..it is not needed if the code gives the possibility to chose the filenames for outputs and inputs)
    
    pathOfExectuable = os.path.split(inputFiles[0])[0]
    nameOfExecutable = os.path.split(executable)[1]
    executeCommand = (os.path.join(pathOfExectuable,nameOfExecutable))
    # the outputfile in this particular code has an hardcoded name.. add it
    outputfile = os.path.join(pathOfExectuable,'RANDoutput')
    return executeCommand,outputfile

  def appendLoadFileExtension(self,fileRoot):
    '''  self explainable '''
    return fileRoot + '.csv'

  def createNewInput(self,currentInputFiles,oriInputFiles,samplerType,**Kwargs):
    '''this generate a new input file depending on which sampler is chosen'''
    import HOBOInputParser
    # dictionary of the samplers (methods used for interpreting the informations coming from the different samplers)
    # as it can be noticed, all the samplers, except the Dynamic Event Tree. point to the same method (pointSampler)
    self._samplersDictionary                          = {}
    self._samplersDictionary['MonteCarlo'           ] = self.pointSamplerForHOBO
    self._samplersDictionary['Grid'                 ] = self.pointSamplerForHOBO
    self._samplersDictionary['LHS'                  ] = self.pointSamplerForHOBO
    self._samplersDictionary['Adaptive'             ] = self.pointSamplerForHOBO
    self._samplersDictionary['StochasticCollocation'] = self.pointSamplerForHOBO
    self._samplersDictionary['DynamicEventTree'     ] = self.DynamicEventTreeForHOBO
    # currentInputFiles is a list of all originals input files...
    # we need to find the right one. We decided a syntax where the first variable entry is the input file name... so let's look for it
    modifDict = self._samplersDictionary[samplerType](**Kwargs)
    historiesFiles = None
    if 'strategy1' in modifDict.keys(): historiesFiles = ['2_temperature.txt','3_fissionrate.txt']
    else: fileNameBody = Kwargs['SampledVars'].keys()[0].split('|')[0]
    
    index = -1
    if not historiesFiles:
      for cnt,inputF in enumerate(currentInputFiles):
        if fileNameBody == os.path.basename(inputF).split(".")[0]:
          index=cnt
          break
      if index == -1: raise IOError('HOBOInterface: ERROR -> the filename with a body name '+ fileNameBody + 'has not been found among the inputfiles ' + str(currentInputFiles))
      parser = HOBOInputParser.HOBOInputParser(currentInputFiles[index])
    else:
      historiesFilesPaths = []
      for filenamei in historiesFiles:
        for cnt,inputF in enumerate(currentInputFiles): 
         if filenamei == os.path.basename(inputF): historiesFilesPaths.append(copy.deepcopy(currentInputFiles[cnt]))
      parser = HOBOInputParser.HOBOInputParser(historiesFilesPaths)  
    parser.modifyOrAdd(modifDict,True)
    temp = str(oriInputFiles[index][:])
    newInputFiles = copy.deepcopy(currentInputFiles)
    # now we make a new directory since the code we are running does not let the user change the input and output file names
    # we are going to copy the new filesinto that directory. Also the executable needs to be copied... (for the same reason)
    if not os.path.exists(os.path.join(os.path.split(temp)[0],Kwargs['prefix'])): os.makedirs(os.path.join(os.path.split(temp)[0],Kwargs['prefix']))
    # for a code that lets the user provide the filenames for the inputs and outputs, it is not needed to copy the inputs not perturbed into the directory
    # here we need to do that because the framework copies those files into the working directory (it is not aware of the newer directory we just created)
    for cnt,filenameToCopy in enumerate(oriInputFiles):
      if cnt != index: 
        shutil.copyfile(filenameToCopy, os.path.join(os.path.split(str(oriInputFiles[cnt][:]))[0],Kwargs['prefix'],os.path.split(str(oriInputFiles[cnt][:]))[1]))
    # copy the executable (remember..it is not needed if the code gives the possibility to chose the filenames for outputs and inputs)
    try: os.remove(os.path.join(os.path.split(temp)[0],Kwargs['prefix'],os.path.basename(Kwargs['executable'])))
    except:pass 
    shutil.copyfile(Kwargs['executable'],os.path.join(os.path.split(temp)[0],Kwargs['prefix'],os.path.basename(Kwargs['executable'])))
    if not historiesFiles:
      newInputFiles[index] = copy.deepcopy(os.path.join(os.path.split(temp)[0],Kwargs['prefix'],os.path.split(temp)[1]))
    else:
      ciccio = []
      for cnt in range(len(oriInputFiles)):
        temp = str(oriInputFiles[cnt][:])
        if os.path.basename(temp) in historiesFiles:
          ciccio.append(copy.deepcopy(os.path.join(os.path.split(temp)[0],Kwargs['prefix'],os.path.split(temp)[1])))
        else:
          newInputFiles[cnt] = copy.deepcopy(os.path.join(os.path.split(temp)[0],Kwargs['prefix'],os.path.split(temp)[1]))
    # change rights of executable
    shutil.copystat(Kwargs['executable'],os.path.join(os.path.split(temp)[0],Kwargs['prefix'],os.path.basename(Kwargs['executable'])))
    if not historiesFiles:
      parser.printInput(newInputFiles[index])
    else:
      parser.printInput(ciccio)   
    return newInputFiles

  def pointSamplerForHOBO(self,**Kwargs):
    #known paramters that define a certain strategy
    knownParams = {'strategy1':['delta_t','Temp','FissionRate']}
    modifDict = {}
    foundKnownParameters = False
    strategy    = None
    T           = None
    FissionRate = None
    Time        = None
    for key in Kwargs['SampledVars']:
      if key.split('|')[0] not in knownParams['strategy1']:
        #1_settings|row|12
        # pathToVariable = list that represents the path to the variable that needs to be changed 
        # what we have inside (remember that this syntax is decided by the the developer is coupling the new code):
        # first entry is the inputfile name that needs to be perturbed (for this simple example, the only file name that is supported is 1_settings.txt)
        # second entry, for this syntax, is only a convinient keyword (row)
        # third entry is the row number that is going to be pertorbed
        pathToVariable = key.split("|") 
        if len(pathToVariable) != 3: raise IOError('HOBOInterface: ERROR -> This interface expects a variable with the format'+
                                                   ' "filename(no extension)|row|rowNumber". Got' + key)
        # we add the perturebed values into a dictionary (or whatever object the developer wants to use) 
        # in a format that is understandable by the input parser (for this particular code) that is provided in another module (or whitin this one)
        modifDict[key] = {'row':int(pathToVariable[2]),'value':Kwargs['SampledVars'][key]}
      else:
        foundKnownParameters = True
        for value in knownParams['strategy1']:
          if key.split('|')[0] in value:
            strategy = 'strategy1'
            break
      if foundKnownParameters:
        if strategy == 'strategy1':
          if  key.split('|')[0] == 'Temp':
            if not T: T = []
            T.append(float(Kwargs['SampledVars'][key]))
          elif key.split('|')[0] == 'FissionRate':
            if not FissionRate: FissionRate = []
            FissionRate.append(float(Kwargs['SampledVars'][key]))      
          elif key.split('|')[0] == 'delta_t':
            if not Time: Time = []
            if len(Time) == 0:Time.append(float(Kwargs['SampledVars'][key]))
            else:Time.append(float(Kwargs['SampledVars'][key])+Time[-1])
          
    if foundKnownParameters: modifDict['strategy1'] = {'T':T,'FissionRate':FissionRate,'time':Time}
    return copy.deepcopy(modifDict)  

  def DynamicEventTreeForHOBO(self,**Kwargs):
    raise NotYetImplemented("DynamicEventTreeForHOBO not yet implemented")
  