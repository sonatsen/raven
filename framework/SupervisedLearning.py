"""
Module containing all supported type of ROM aka Surrogate Models etc
here we intend ROM as super-visioned learning,
where we try to understand the underlying model by a set of labeled sample
a sample is composed by (feature,label) that is easy translated in (input,output)
"""
#for future compatibility with Python 3--------------------------------------------------------------
from __future__ import division, print_function, unicode_literals, absolute_import
import warnings
warnings.simplefilter('default',DeprecationWarning)
#End compatibility block for Python 3----------------------------------------------------------------

#External Modules------------------------------------------------------------------------------------
from sklearn import linear_model
from sklearn import svm
from sklearn import multiclass
from sklearn import naive_bayes
from sklearn import neighbors
from sklearn import qda
from sklearn import tree
from sklearn import lda
from sklearn import gaussian_process
import sys
import numpy as np
import numpy
import abc
import ast
import pickle as pk
from operator import itemgetter
from collections import OrderedDict

from scipy import spatial
from sklearn.neighbors.kde import KernelDensity
import math
#External Modules End--------------------------------------------------------------------------------

#Internal Modules------------------------------------------------------------------------------------
import utils
import MessageHandler
import TreeStructure
interpolationND = utils.find_interpolationND()
#Internal Modules End--------------------------------------------------------------------------------

class superVisedLearning(utils.metaclass_insert(abc.ABCMeta),MessageHandler.MessageUser):
  """
  This is the general interface to any superVisedLearning learning method.
  Essentially it contains a train method and an evaluate method
  """
  returnType      = '' #this describe the type of information generated the possibility are 'boolean', 'integer', 'float'
  qualityEstType  = [] #this describe the type of estimator returned known type are 'distance', 'probability'. The values are returned by the self.__confidenceLocal__(Features)
  ROMtype         = '' #the broad class of the interpolator

  @staticmethod
  def checkArrayConsistency(arrayin):
    """
    This method checks the consistency of the in-array
    @ In, object... It should be an array
    @ Out, tuple, tuple[0] is a bool (True -> everything is ok, False -> something wrong), tuple[1], string ,the error mesg
    """
    if type(arrayin) != numpy.ndarray: return (False,' The object is not a numpy array')
    if len(arrayin.shape) > 1: return(False, ' The array must be 1-d')
    return (True,'')

  def __init__(self,messageHandler,**kwargs):
    """
    A constructor that will appropriately intialize a supervised learning object
    @In, messageHandler: a MessageHandler object in charge of raising errors,
                         and printing messages
    @In, kwargs: an arbitrary list of kwargs
    """
    self.printTag = 'Supervised'
    self.messageHandler = messageHandler
    #booleanFlag that controls the normalization procedure. If true, the normalization is performed. Default = True
    if kwargs != None: self.initOptionDict = kwargs
    else             : self.initOptionDict = {}
    if 'Features' not in self.initOptionDict.keys(): self.raiseAnError(IOError,'Feature names not provided')
    if 'Target'   not in self.initOptionDict.keys(): self.raiseAnError(IOError,'Target name not provided')
    self.features = self.initOptionDict['Features'].split(',')
    self.target   = self.initOptionDict['Target'  ]
    self.initOptionDict.pop('Target')
    self.initOptionDict.pop('Features')
    self.verbosity = self.initOptionDict['verbosity'] if 'verbosity' in self.initOptionDict else None
    if self.features.count(self.target) > 0: self.raiseAnError(IOError,'The target and one of the features have the same name!')
    #average value and sigma are used for normalization of the feature data
    #a dictionary where for each feature a tuple (average value, sigma)
    self.muAndSigmaFeatures = {}
    #these need to be declared in the child classes!!!!
    self.amITrained         = False

  # def addInitParams(self,tempDict):
  #   tempDict['messageHandler'] = self.messageHandler
  #   tempDict['printTag'] = self.printTag
  #   tempDict['features'] = self.features
  #   tempDict['target'] = self.target
  #   tempDict['verbosity'] = self.verbosity
  #   tempDict['amITrained'] = self.amITrained
  #   tempDict['muAndSigmaFeatures'] = self.muAndSigmaFeatures
  #   tempDict['returnType'] = self.returnType
  #   tempDict['qualityEstType'] = self.qualityEstType
  #   tempDict['ROMtype'] = self.ROMtype

  # def __getstate__(self):
  #   state = {}
  #   self.addInitParams(state)
  #   return state

  # def __setstate__(self,newState):
  #   self.features           = newState.pop('features'          )
  #   self.target             = newState.pop('target'            )
  #   self.verbosity          = newState.pop('verbosity'         )
  #   self.amITrained         = newState.pop('amITrained'        )
  #   self.muAndSigmaFeatures = newState.pop('muAndSigmaFeatures')
  #   self.returnType         = newState.pop('returnType'        )
  #   self.qualityEstType     = newState.pop('qualityEstType'    )
  #   self.ROMtype            = newState.pop('ROMtype'           )
  #   self.printTag           = newState.pop('printTag'          )

  def initialize(self,idict):
    pass #Overloaded by (at least) GaussPolynomialRom

  def train(self,tdict):
    """
      Method to perform the training of the superVisedLearning algorithm
      NB.the superVisedLearning object is committed to convert the dictionary that is passed (in), into the local format
      the interface with the kernels requires. So far the base class will do the translation into numpy
      @ In, tdict, training dictionary
      @ Out, None
    """
    if type(tdict) != dict: self.raiseAnError(TypeError,'In method "train", the training set needs to be provided through a dictionary. Type of the in-object is ' + str(type(tdict)))
    names, values  = list(tdict.keys()), list(tdict.values())
    if self.target in names: targetValues = values[names.index(self.target)]
    else                   : self.raiseAnError(IOError,'The output sought '+self.target+' is not in the training set')
    # check if the targetValues are consistent with the expected structure
    resp = self.checkArrayConsistency(targetValues)
    if not resp[0]: self.raiseAnError(IOError,'In training set for target '+self.target+':'+resp[1])
    # construct the evaluation matrixes
    featureValues = np.zeros(shape=(targetValues.size,len(self.features)))
    for cnt, feat in enumerate(self.features):
      if feat not in names: self.raiseAnError(IOError,'The feature sought '+feat+' is not in the training set')
      else:
        resp = self.checkArrayConsistency(values[names.index(feat)])
        if not resp[0]: self.raiseAnError(IOError,'In training set for feature '+feat+':'+resp[1])
        if values[names.index(feat)].size != featureValues[:,0].size:
          self.raiseAWarning('feature values:',featureValues[:,0].size,tag='ERROR')
          self.raiseAWarning('target values:',values[names.index(feat)].size,tag='ERROR')
          self.raiseAnError(IOError,'In training set, the number of values provided for feature '+feat+' are != number of target outcomes!')
        self._localNormalizeData(values,names,feat)
        if self.muAndSigmaFeatures[feat][1]==0: self.muAndSigmaFeatures[feat] = (self.muAndSigmaFeatures[feat][0],np.max(np.absolute(values[names.index(feat)])))
        if self.muAndSigmaFeatures[feat][1]==0: self.muAndSigmaFeatures[feat] = (self.muAndSigmaFeatures[feat][0],1.0)
        featureValues[:,cnt] = (values[names.index(feat)] - self.muAndSigmaFeatures[feat][0])/self.muAndSigmaFeatures[feat][1]
    self.__trainLocal__(featureValues,targetValues)
    self.amITrained = True

  def _localNormalizeData(self,values,names,feat):
    """
    Method to normalize data based on the mean and standard deviation.  If undesired for a particular ROM,
    this method can be overloaded to simply pass (see, e.g., GaussPolynomialRom).
    @ In, values, list of feature values (from tdict)
    @ In, names, names of features (from tdict)
    @ In, feat, list of features (from ROM)
    @ Out, None
    """
    self.muAndSigmaFeatures[feat] = (np.average(values[names.index(feat)]),np.std(values[names.index(feat)]))

  def confidence(self,edict):
    """
    This call is used to get an estimate of the confidence in the prediction.
    The base class self.confidence will translate a dictionary into numpy array, then call the local confidence
    @ In, edict, evaluation dictionary
    @ Out, float, the confidence
    """
    if type(edict) != dict: self.raiseAnError(IOError,'method "confidence". The inquiring set needs to be provided through a dictionary. Type of the in-object is ' + str(type(edict)))
    names, values   = list(edict.keys()), list(edict.values())
    for index in range(len(values)):
      resp = self.checkArrayConsistency(values[index])
      if not resp[0]: self.raiseAnError(IOError,'In evaluate request for feature '+names[index]+':'+resp[1])
    featureValues = np.zeros(shape=(values[0].size,len(self.features)))
    for cnt, feat in enumerate(self.features):
      if feat not in names: self.raiseAnError(IOError,'The feature sought '+feat+' is not in the evaluate set')
      else:
        resp = self.checkArrayConsistency(values[names.index(feat)])
        if not resp[0]: self.raiseAnError(IOError,'In training set for feature '+feat+':'+resp[1])
        featureValues[:,cnt] = values[names.index(feat)]
    return self.__confidenceLocal__(featureValues)

  def evaluate(self,edict):
    """
    Method to perform the evaluation of a point or a set of points through the previous trained superVisedLearning algorithm
    NB.the superVisedLearning object is committed to convert the dictionary that is passed (in), into the local format
    the interface with the kernels requires.
    @ In, edict, evaluation dictionary
    @ Out, numpy array of evaluated points
    """
    if type(edict) != dict: self.raiseAnError(IOError,'method "evaluate". The evaluate request/s need/s to be provided through a dictionary. Type of the in-object is ' + str(type(edict)))
    names, values  = list(edict.keys()), list(edict.values())
    for index in range(len(values)):
      resp = self.checkArrayConsistency(values[index])
      if not resp[0]: self.raiseAnError(IOError,'In evaluate request for feature '+names[index]+':'+resp[1])
    # construct the evaluation matrix
    featureValues = np.zeros(shape=(values[0].size,len(self.features)))
    for cnt, feat in enumerate(self.features):
      if feat not in names: self.raiseAnError(IOError,'The feature sought '+feat+' is not in the evaluate set')
      else:
        resp = self.checkArrayConsistency(values[names.index(feat)])
        if not resp[0]: self.raiseAnError(IOError,'In training set for feature '+feat+':'+resp[1])
        featureValues[:,cnt] = ((values[names.index(feat)] - self.muAndSigmaFeatures[feat][0]))/self.muAndSigmaFeatures[feat][1]
    return self.__evaluateLocal__(featureValues)

  def reset(self):
    """override this method to re-instance the ROM"""
    self.amITrained = False
    self.__resetLocal__()

  def returnInitialParameters(self):
    """override this method to return the fix set of parameters of the ROM"""
    iniParDict = dict(list(self.initOptionDict.items()) + list({'returnType':self.__class__.returnType,'qualityEstType':self.__class__.qualityEstType,'Features':self.features,
                                             'Target':self.target,'returnType':self.__class__.returnType}.items()) + list(self.__returnInitialParametersLocal__().items()))
    return iniParDict

  def returnCurrentSetting(self):
    """return the set of parameters of the ROM that can change during simulation"""
    return dict({'Trained':self.amITrained}.items() + self.__CurrentSettingDictLocal__().items())

  def printXML(self,rootnode,options=None):
    """
      Allows the SVE to put whatever it wants into an XML to print to file.
      @ In, rootnode, the root node of an XML tree to print to
      @ In, options, dict of string-based options to use, including filename, things to print, etc
      @ Out, treedict, dict of strings to be printed
    """
    node = TreeStructure.Node(self.target)
    rootnode.appendBranch(node)
    self._localPrintXML(node,options)

  def _localPrintXML(self,node,options=None):
    """
      Specific local method for printing anything desired to xml file.  Overwrite in inheriting classes.
      @ In, node, the node to which strings should have text added
      @ In, options, dict of string-based options to use, including filename, things to print, etc
      @ Out, treedict, dict of strings to be printed
    """
    #if treedict=={}: treedict={'PrintOptions':'ROM of type '+str(self.printTag.strip())+' has no special output options.'}
    node.addText('ROM of type '+str(self.printTag.strip())+' has no special output options.')

  @abc.abstractmethod
  def __trainLocal__(self,featureVals,targetVals):
    """
    Perform training on samples in featureVals with responses y.
    For an one-class model, +1 or -1 is returned.

    @In, featureVals, {array-like, sparse matrix}, shape=[n_samples, n_features],
      an array of input feature values
    @ Out, targetVals, array, shape = [n_samples], an array of output target
      associated with the corresponding points in featureVals
    """

  @abc.abstractmethod
  def __confidenceLocal__(self,featureVals):
    """
    This should return an estimation of the quality of the prediction.
    This could be distance or probability or anything else, the type needs to be declared in the variable cls.qualityEstType
    @ In, featureVals, 2-D numpy array [n_samples,n_features]
    @ Out, float, the confidence
    """

  @abc.abstractmethod
  def __evaluateLocal__(self,featureVals):
    """
    @ In,  featureVals, 2-D numpy array [n_samples,n_features]
    @ Out, targetVals , 1-D numpy array [n_samples]
    """

  @abc.abstractmethod
  def __resetLocal__(self,featureVals):
    """After this method the ROM should be described only by the initial parameter settings"""

  @abc.abstractmethod
  def __returnInitialParametersLocal__(self):
    """this should return a dictionary with the parameters that could be possible not in self.initOptionDict"""

  @abc.abstractmethod
  def __returnCurrentSettingLocal__(self):
    """override this method to pass the set of parameters of the ROM that can change during simulation"""
#
#
#
class NDinterpolatorRom(superVisedLearning):
  """
  A Reduced Order Model for interpolating N-dimensional data
  """
  def __init__(self,messageHandler,**kwargs):
    """
    A constructor that will appropriately intialize a supervised learning object
    @In, messageHandler: a MessageHandler object in charge of raising errors,
                         and printing messages
    @In, kwargs: an arbitrary dictionary of keywords and values
    """
    superVisedLearning.__init__(self,messageHandler,**kwargs)
    self.interpolator = None  # pointer to the C++ (crow) interpolator
    self.featv        = None  # list of feature variables
    self.targv        = None  # list of target variables
    self.printTag = 'ND Interpolation ROM'


  def __getstate__(self):
    """
    Overwrite state (for pickle-ing)
    we do not pickle the HDF5 (C++) instance
    but only the info to re-load it
    @ In, None
    @ Out, None
    """
    # capture what is normally pickled
    state = self.__dict__.copy()
    if 'interpolator' in state.keys():
      a = state.pop("interpolator")
      del a
    return state

  def __setstate__(self, newstate):
    """
    Initialize the ROM with the data contained in newstate
    @ In, newstate, dic, it contains all the information needed by the ROM to be initialized
    @ Out, None
    """
    self.__dict__.update(newstate)
    self.__initLocal__()
    self.__trainLocal__(self.featv,self.targv)

  def __trainLocal__(self,featureVals,targetVals):
    """
    Perform training on samples in featureVals with responses y.
    For an one-class model, +1 or -1 is returned.

    @In, featureVals, {array-like, sparse matrix}, shape=[n_samples, n_features],
      an array of input feature values
    @ Out, targetVals, array, shape = [n_samples], an array of output target
      associated with the corresponding points in featureVals
    """
    self.featv, self.targv = featureVals,targetVals
    featv = interpolationND.vectd2d(featureVals[:][:])
    targv = interpolationND.vectd(targetVals)

    self.interpolator.fit(featv,targv)

  def __confidenceLocal__(self,featureVals):
    """
    This should return an estimation of the quality of the prediction.
    @ In, featureVals, 2-D numpy array [n_samples,n_features]
    @ Out, float, the confidence
    """
    self.raiseAnError(NotImplementedError,'NDinterpRom   : __confidenceLocal__ method must be implemented!')

  def __evaluateLocal__(self,featureVals):
    """
    Perform regression on samples in featureVals.
    For an one-class model, +1 or -1 is returned.
    @ In, numpy.array 2-D, features
    @ Out, numpy.array 1-D, predicted values
    """
    prediction = np.zeros(featureVals.shape[0])
    for n_sample in range(featureVals.shape[0]):
      featv = interpolationND.vectd(featureVals[n_sample][:])
      prediction[n_sample] = self.interpolator.interpolateAt(featv)
      self.raiseAMessage('NDinterpRom   : Prediction by ' + self.__class__.ROMtype + '. Predicted value is ' + str(prediction[n_sample]))
    return prediction

  def __returnInitialParametersLocal__(self):
    """there are no possible default parameters to report"""
    localInitParam = {}
    return localInitParam

  def __returnCurrentSettingLocal__(self):
    """ Exposes access to the current settings of this ROM object """
    self.raiseAnError(NotImplementedError,'NDinterpRom   : __returnCurrentSettingLocal__ method must be implemented!')
#
#
#
#
class GaussPolynomialRom(superVisedLearning):
  def __confidenceLocal__(self,edict):
    """Require by inheritance, unused.
    @ In, None
    @ Out, None
    """
    pass

  def __resetLocal__(self):
    """Require by inheritance, unused.
    @ In, None
    @ Out, None
    """
    pass

  def __returnCurrentSettingLocal__(self):
    """Require by inheritance, unused.
    @ In, None
    @ Out, None
    """
    pass

  def __initLocal__(self):
    """ Method used to add additional initialization features used by pickling
    @ In, None
    @ Out, None
    """
    pass

  def __init__(self,messageHandler,**kwargs):
    """Initializes class.
    @ In, kwargs, dict of XML inputs from ROM
    @ Out, None
    """
    superVisedLearning.__init__(self,messageHandler,**kwargs)
    self.initialized   = False #only True once self.initialize has been called
    self.interpolator  = None #FIXME what's this?
    self.printTag      = 'GAUSSgpcROM('+self.target+')'
    self.indexSetType  = None #string of index set type, TensorProduct or TotalDegree or HyperbolicCross
    self.indexSetVals  = []   #list of tuples, custom index set to use if CustomSet is the index set type
    self.maxPolyOrder  = None #integer of relative maximum polynomial order to use in any one dimension
    self.itpDict       = {}   #dict of quad,poly,weight choices keyed on varName
    self.norm          = None #combined distribution normalization factors (product)
    self.sparseGrid    = None #Quadratures.SparseGrid object, has points and weights
    self.distDict      = None #dict{varName: Distribution object}, has point conversion methods based on quadrature
    self.quads         = None #dict{varName: Quadrature object}, has keys for distribution's point conversion methods
    self.polys         = None #dict{varName: OrthoPolynomial object}, has polynomials for evaluation
    self.indexSet      = None #array of tuples, polynomial order combinations
    self.polyCoeffDict = None #dict{index set point, float}, polynomial combination coefficients for each combination
    self.numRuns       = None #number of runs to generate ROM; default is len(self.sparseGrid)
    self.itpDict       = {}   #dict{varName: dict{attribName:value} }
    self.featv         = None  # list of feature variables
    self.targv         = None  # list of target variables
    self.sparseGridType    = 'smolyak' #type of sparse quadrature to use,default smolyak
    self.sparseQuadOptions = ['smolyak','tensor'] # choice of sparse quadrature construction methods

    for key,val in kwargs.items():
      if key=='IndexSet':self.indexSetType = val
      elif key=='IndexPoints':
        self.indexSetVals=[]
        strIndexPoints = val.strip()
        strIndexPoints = strIndexPoints.replace(' ','').replace('\n','').strip('()')
        strIndexPoints = strIndexPoints.split('),(')
        self.raiseADebug(strIndexPoints)
        for s in strIndexPoints:
          self.indexSetVals.append(tuple(int(i) for i in s.split(',')))
        self.raiseADebug('points',self.indexSetVals)
      elif key=='PolynomialOrder': self.maxPolyOrder = val
      elif key=='Interpolation':
        for var,val in val.items():
          self.itpDict[var]={'poly'  :'DEFAULT',
                             'quad'  :'DEFAULT',
                             'weight':'1'}
          for atrName,atrVal in val.items():
            if atrName in ['poly','quad','weight']: self.itpDict[var][atrName]=atrVal
            else: self.raiseAnError(IOError,'Unrecognized option: '+atrName)
      elif key == 'SparseGrid':
        if val.lower() not in self.sparseQuadOptions:
          self.raiseAnError(IOError,'No such sparse quadrature implemented: %s.  Options are %s.' %(val,str(self.sparseQuadOptions)))
        self.sparseGridType = val

    if not self.indexSetType:
      self.raiseAnError(IOError,'No IndexSet specified!')
    if self.indexSetType=='Custom':
      if len(self.indexSetVals)<1: self.raiseAnError(IOError,'If using CustomSet, must specify points in <IndexPoints> node!')
      else:
        for i in self.indexSetVals:
          if len(i)<len(self.features): self.raiseAnError(IOError,'CustomSet points',i,'is too small!')
    if not self.maxPolyOrder:
      self.raiseAnError(IOError,'No maxPolyOrder specified!')
    if self.maxPolyOrder < 1:
      self.raiseAnError(IOError,'Polynomial order cannot be less than 1 currently.')

  def _localPrintXML(self,node,options=None):
    """
      Adds requested entries to XML node.
      @ In, node, XML node to which entries will be added
      @ In, options, dict (optional), list of requests and options
      @ Out, None
    """
    if not self.amITrained: self.raiseAnError(RuntimeError,'ROM is not yet trained!')
    self.mean=None
    canDo = ['mean','variance','numRuns','polyCoeffs']
    if 'what' in options.keys():
      requests = list(o.strip() for o in options['what'].split(','))
      if 'all' in requests: requests = canDo
      for request in requests:
        request=request.strip()
        newnode = TreeStructure.Node(request)
        if   request.lower() in ['mean','expectedvalue']:
          if self.mean == None: self.mean = self.__evaluateMoment__(1)
          newnode.setText(self.mean)
        elif request.lower() in ['variance']:
          if self.mean == None: self.mean = self.__evaluateMoment__(1)
          newnode.setText(self.__evaluateMoment__(2) - self.mean*self.mean)
        elif request.lower() in ['numruns']:
          if self.numRuns!=None: newnode.setText(self.numRuns)
          else: newnode.setText(len(self.sparseGrid))
        elif request.lower() in ['polycoeffs']:
          vnode = TreeStructure.Node('inputVariables')
          vnode.text = ','.join(self.features)
          newnode.appendBranch(vnode)
          keys = self.polyCoeffDict.keys()
          keys.sort()
          for key in keys:
            cnode = TreeStructure.Node('_'+'_'.join(str(k) for k in key)+'_')
            cnode.setText(self.polyCoeffDict[key])
            newnode.appendBranch(cnode)
        else:
          self.raiseAWarning('ROM does not know how to return '+request)
          newnode.setText('not found')
        node.appendBranch(newnode)

  def _localNormalizeData(self,values,names,feat):
    """Overwrites default normalization procedure.
    @ In, values, unused
    @ In, names, unused
    @ In, feat, feature to (not) normalize
    @ Out, None
    """
    self.muAndSigmaFeatures[feat] = (0.0,1.0)

  def interpolationInfo(self):
    """Returns the interpolation information
    @ In, None
    @ Out, dictionary of interpolation information
    """
    return dict(self.itpDict)

  def initialize(self,idict):
    """Initializes the instance.
    @ In, idict, dict of objects needed to initalize
    @ Out, None
    """
    self.sparseGrid     = idict.get('SG'        ,None)
    self.distDict       = idict.get('dists'     ,None)
    self.quads          = idict.get('quads'     ,None)
    self.polys          = idict.get('polys'     ,None)
    self.indexSet       = idict.get('iSet'      ,None)
    self.numRuns        = idict.get('numRuns'   ,None)
    #make sure requireds are not None
    if self.sparseGrid is None: self.raiseAnError(RuntimeError,'Tried to initialize without key object "SG"   ')
    if self.distDict   is None: self.raiseAnError(RuntimeError,'Tried to initialize without key object "dists"')
    if self.quads      is None: self.raiseAnError(RuntimeError,'Tried to initialize without key object "quads"')
    if self.polys      is None: self.raiseAnError(RuntimeError,'Tried to initialize without key object "polys"')
    if self.indexSet   is None: self.raiseAnError(RuntimeError,'Tried to initialize without key object "iSet" ')
    self.initialized = True

  def _multiDPolyBasisEval(self,orders,pts):
    """Evaluates each polynomial set at given orders and points, returns product.
    @ In orders, tuple(int), polynomial orders to evaluate
    @ In pts, tuple(float), values at which to evaluate polynomials
    @ Out, float, product of polynomial evaluations
    """
    tot=1
    for i,(o,p) in enumerate(zip(orders,pts)):
      varName = self.sparseGrid.varNames[i]
      tot*=self.polys[varName](o,p)
    return tot

  def __trainLocal__(self,featureVals,targetVals):
    """Trains ROM.
    @ In, featureVals, list, feature values
    @ In, targetVals, list, target values
    """
    #check to make sure ROM was initialized
    if not self.initialized:
      self.raiseAnError(RuntimeError,'ROM has not yet been initialized!  Has the Sampler associated with this ROM been used?')
    self.raiseADebug('training',self.features,'->',self.target)
    self.featv, self.targv = featureVals,targetVals
    self.polyCoeffDict={}
    #check equality of point space
    fvs = []
    tvs=[]
    sgs = list(self.sparseGrid.points())
    missing=[]
    for pt in sgs:
      found,idx,point = utils.NDInArray(featureVals,pt)
      if found:
        fvs.append(point)
        tvs.append(targetVals[idx])
      else:
        missing.append(pt)
    if len(missing)>0:
      msg='\n'
      msg+='DEBUG missing feature vals:\n'
      for i in missing:
        msg+='  '+str(i)+'\n'
      self.raiseADebug(msg)
      self.raiseADebug('sparse:',sgs)
      self.raiseADebug('solns :',fvs)
      self.raiseAnError(IOError,'input values do not match required values!')
    #make translation matrix between lists
    translate={}
    for i in range(len(fvs)):
      translate[tuple(fvs[i])]=sgs[i]
    self.norm = np.prod(list(self.distDict[v].measureNorm(self.quads[v].type) for v in self.distDict.keys()))
    #make polynomials
    for i,idx in enumerate(self.indexSet):
      idx=tuple(idx)
      self.polyCoeffDict[idx]=0
      wtsum=0
      for pt,soln in zip(fvs,tvs):
        stdPt = np.zeros(len(pt))
        for i,p in enumerate(pt):
          varName = self.sparseGrid.varNames[i]
          stdPt[i] = self.distDict[varName].convertToQuad(self.quads[varName].type,p)
        wt = self.sparseGrid.weights(translate[tuple(pt)])
        self.polyCoeffDict[idx]+=soln*self._multiDPolyBasisEval(idx,stdPt)*wt
      self.polyCoeffDict[idx]*=self.norm
    self.amITrained=True

  def printPolyDict(self,printZeros=False):
    """Human-readable version of the polynomial chaos expansion.
    @ In printZeros,boolean,optional flag for printing even zero coefficients
    @ Out, None, None
    """
    data=[]
    for idx,val in self.polyCoeffDict.items():
      if abs(val) > 1e-12 or printZeros:
        data.append([idx,val])
    data.sort()
    self.raiseADebug('polyDict for ['+self.target+'] with inputs '+str(self.features)+':')
    for idx,val in data:
      self.raiseADebug('    '+str(idx)+' '+str(val))

  def checkForNonzeros(self,tol=1e-12):
    """
      Checks poly coefficient dictionary for nonzero entries.
      @ In, tol, float(optional), the tolerance under which is zero (default 1e-12)
      @ Out, list(tuple), the indices and values of the nonzero coefficients
    """
    data=[]
    for idx,val in self.polyCoeffDict.items():
      if round(val,11) !=0:
        data.append([idx,val])
    return data

  def __variance__(self):
    """returns the variance of the ROM.
    @ In, None
    @ Out, float, variance
    """
    mean = self.__evaluateMoment__(1)
    return self.__evaluateMoment__(2) - mean*mean

  def __evaluateMoment__(self,r):
    """Use the ROM's built-in method to calculate moments.
    @ In r, int, moment to calculate
    @ Out, float, evaluation of moment
    """
    #TODO is there a faster way still to do this?
    if r==1: return self.polyCoeffDict[tuple([0]*len(self.features))]
    elif r==2: return sum(s**2 for s in self.polyCoeffDict.values())
    tot=0
    for pt,wt in self.sparseGrid:
      tot+=self.__evaluateLocal__([pt])**r*wt
    tot*=self.norm
    return tot

  def __evaluateLocal__(self,featureVals):
    """ Evaluates a point.
    @ In, featureVals, list of values at which to evaluate the ROM
    @ Out, float, the evaluated point
    """
    featureVals=featureVals[0]
    tot=0
    stdPt = np.zeros(len(featureVals))
    for p,pt in enumerate(featureVals):
      varName = self.sparseGrid.varNames[p]
      stdPt[p] = self.distDict[varName].convertToQuad(self.quads[varName].type,pt)
    for idx,coeff in self.polyCoeffDict.items():
      tot+=coeff*self._multiDPolyBasisEval(idx,stdPt)
    return tot

  def _printPolynomial(self):
    """ Prints each polynomial for each coefficient.
    @ In, None
    @ Out, None
    """
    self.raiseADebug('Coeff Idx')
    for idx,coeff in self.polyCoeffDict.items():
      if abs(coeff)<1e-12: continue
      self.raiseADebug(str(idx))
      for i,ix in enumerate(idx):
        var = self.features[i]
        self.raiseADebug(self.polys[var][ix]*coeff,'|',var)

  def __returnInitialParametersLocal__(self):
    """Required by inheritance, but not used.
    @ In, None
    @ Out, None
    """
    return {}
#
#
#
#
class HDMRRom(GaussPolynomialRom):
  """High-Dimention Model Reduction reduced order model.  Constructs model based on subsets of the input space."""
  def __confidenceLocal__(self,edict):
    """Require by inheritance, unused.
    @ In, edict, unused
    @ Out, None
    """
    pass

  def __resetLocal__(self):
    """Require by inheritance, unused.
    @ In, None
    @ Out, None
    """
    pass

  def __returnCurrentSettingLocal__(self):
    """Require by inheritance, unused.
    @ In, None
    @ Out, None
    """
    pass

  def __init__(self,messageHandler,**kwargs):
    """Initializes class.
    @ In, kwargs, dict of XML inputs from ROM
    @ Out, None
    """
    GaussPolynomialRom.__init__(self,messageHandler,**kwargs)
    self.initialized   = False #true only when self.initialize has been called
    self.printTag      = 'HDMR_ROM('+self.target+')'
    self.sobolOrder    = None #depth of HDMR/Sobol expansion
    self.ROMs          = {}   #dict of GaussPolyROM objects keyed by combination of vars that make them up
    self.sdx           = None #dict of sobol sensitivity coeffs, keyed on order and tuple(varnames)
    self.mean          = None #mean, store to avoid recalculation
    self.variance      = None #variance, store to avoid recalculation
    self.anova         = None #converted true ANOVA terms, stores coefficients not polynomials
    self.partialVariances = None #partial variance contributions

    for key,val in kwargs.items():
      if key=='SobolOrder': self.sobolOrder = int(val)

  def _localPrintXML(self,node,options=None):
    """
      Adds requested entries to XML node.
      @ In, node, XML node to which entries will be added
      @ In, options, dict (optional), list of requests and options
      @ Out, None
    """
    if not self.amITrained: self.raiseAnError(RuntimeError,'ROM is not yet trained!')
    self.mean=None
    canDo = ['mean','variance','indices','numRuns']
    if 'what' in options.keys():
      requests = list(o.strip() for o in options['what'].split(','))
      if 'all' in requests: requests = canDo
      for request in requests:
        request=request.strip()
        newNode = TreeStructure.Node(request)
        if request.lower() in ['mean','expectedvalue']: newNode.setText(self.__mean__())
        elif request.lower() in ['variance']:
          newNode.setText(self.__variance__())
          newNode.name = 'variance'
        elif request.lower() in ['indices']:
          pcts,totPct,totVar = self.getPercentSensitivities(returnTotal=True)
          vNode = TreeStructure.Node('tot_variance')
          vNode.setText(totVar)
          newNode.appendBranch(vNode)
          #split into two sets, significant and insignificant
          entries = []
          insig = []
          for combo,sens in pcts.items():
            if abs(sens)>1e-10:
              entries.append((combo,sens))
            else:
              insig.append((combo,sens))
          entries.sort(key=itemgetter(0))
          entries.sort(key=lambda x: abs(x[1]),reverse=True)
          insig.sort(key=itemgetter(0))
          #trim (insignificat and less than zero) to zero
          for e,entry in enumerate(insig):
            if entry[1]<0:
              insig[e] = (insig[e][0],0.0)
          def addSensBranch(combo,sens):
            """
            Adds a sensitivity branch to the printed XML tree
            @ In, combo, tuple(str), the subset dimensions
            @ In, sens, float, the sensitivity
            """
            sNode = TreeStructure.Node('variables')
            svNode = TreeStructure.Node('index')
            svNode.setText(sens)
            sNode.appendBranch(svNode)
            sNode.setText(','.join(combo))
            newNode.appendBranch(sNode)
          # end method
          for combo,sens in entries:
            addSensBranch(combo,sens)
          for combo,sens in insig:
            addSensBranch(combo,sens)
          newNode.name="Sobol_indices"
        elif request.lower() in ['numruns']:
          newNode.setText(self.numRuns)
        else:
          self.raiseAWarning('ROM does not know how to return '+request)
          newNode.setText('not found')
        node.appendBranch(newNode)

  def initialize(self,idict):
    """Initializes the instance.
    @ In, idict, dict of objects needed to initalize
    @ Out, None
    """
    for key,value in idict.items():
      if   key == 'ROMs'   : self.ROMs       = value
      elif key == 'dists'  : self.distDict   = value
      elif key == 'quads'  : self.quads      = value
      elif key == 'polys'  : self.polys      = value
      elif key == 'refs'   : self.references = value
      elif key == 'numRuns': self.numRuns    = value
    self.initialized = True

  def __trainLocal__(self,featureVals,targetVals):
    """
      Because HDMR rom is a collection of sub-roms, we call sub-rom "train" to do what we need it do.
      @ In, featureVals, dict, training feature values
      @ In, targetVals, dict, training target values
      @ Out, None
    """
    if not self.initialized:
      self.raiseAnError(RuntimeError,'ROM has not yet been initialized!  Has the Sampler associated with this ROM been used?')
    ft={}
    for i in range(len(featureVals)):
      ft[tuple(featureVals[i])]=targetVals[i]
    #get the reference case
    self.refpt = tuple(self.__fillPointWithRef((),[]))
    self.refSoln = ft[self.refpt]
    for combo,rom in self.ROMs.items():
      subtdict={}
      for c in combo: subtdict[c]=[]
      subtdict[self.target]=[]
      SG = rom.sparseGrid
      fvals=np.zeros([len(SG),len(combo)])
      tvals=np.zeros(len(SG))
      for i in range(len(SG)):
        getpt=tuple(self.__fillPointWithRef(combo,SG[i][0]))
        tvals[i] = ft[getpt]
        for fp,fpt in enumerate(SG[i][0]):
          fvals[i][fp] = fpt
      for i,c in enumerate(combo):
        subtdict[c] = fvals[:,i]
      subtdict[self.target] = tvals
      rom.train(subtdict)

    #make ordered list of combos for use later
    maxLevel = max(list(len(combo) for combo in self.ROMs.keys()))
    self.combos = []
    for i in range(maxLevel+1):
      self.combos.append([])
    for combo in self.ROMs.keys():
      self.combos[len(combo)].append(combo)

    #list of term objects
    self.terms = {():[]}  # each entry will look like 'x1,x2':('x1','x2'), missing the reference entry
    for l in range(1,maxLevel+1):
      for romName in self.combos[l]:
        self.terms[romName] = []
        # add subroms -> does this get referenece case, too?
        for key in self.terms.keys():
          if set(key).issubset(set(romName)) and key!=romName:
            self.terms[romName].append(key)
    #reduce terms
    self.reducedTerms = {}
    for term in self.terms.keys():
      self._collectTerms(term,self.reducedTerms)
    #remove zero entries
    self._removeZeroTerms(self.reducedTerms)

    self.amITrained = True

  def __fillPointWithRef(self,combo,pt):
    """Given a "combo" subset of the full input space and a partially-filled
       point within that space, fills the rest of space with the reference
       cut values.
       @ In, combo, tuple of strings, names of subset dimensions
       @ In, pt, list of floats, values of points in subset dimension
       @ Out, newpt, full point in input dimension space on cut-hypervolume
    """
    newpt=np.zeros(len(self.features))
    for v,var in enumerate(self.features):
      if var in combo:
        newpt[v] = pt[combo.index(var)]
      else:
        newpt[v] = self.references[var]
    return newpt

  def __fillIndexWithRef(self,combo,pt):
    """Given a "combo" subset of the full input space and a partially-filled
       polynomial order index within that space, fills the rest of index with zeros.
       @ In, combo, tuple of strings, names of subset dimensions
       @ In, pt, list of floats, values of points in subset dimension
       @ Out, newpt, full index in input dimension space on cut-hypervolume
    """
    #print('Expanding:',combo,pt,self.features)
    newpt=np.zeros(len(self.features),dtype=int)
    #if combo == (): return tuple(newpt)
    for v,var in enumerate(self.features):
      if var in combo:
        newpt[v] = pt[combo.index(var)]
    #print('  Arrived at:',newpt)
    return tuple(newpt)

  def __evaluateLocal__(self,featureVals):
    """ Evaluates a point.
    @ In, featureVals, list of values at which to evaluate the ROM
    @ Out, float, the evaluated point
    """
    #am I trained?
    if not self.amITrained: self.raiseAnError(IOError,'Cannot evaluate, as ROM is not trained!')
    tot = 0
    for term,mult in self.reducedTerms.items():
      if term == ():
        tot += self.refSoln
      else:
        cutVals = [list(featureVals[0][self.features.index(j)] for j in term)]
        tot += self.ROMs[term].__evaluateLocal__(cutVals)*mult
    return tot

  def __mean__(self):
    """The Cut-HDMR approximation can return its mean easily.
    @ In, None
    @ Out, float, the mean
    """
    if not self.amITrained: self.raiseAnError(IOError,'Cannot evaluate mean, as ROM is not trained!')
    return self._calcMean(self.reducedTerms)

  def __variance__(self):
    """The Cut-HDMR approximation can return its variance somewhat easily.
    @ In, None
    @ Out, float, the variance
    """
    if not self.amITrained: self.raiseAnError(IOError,'Cannot evaluate variance, as ROM is not trained!')
    self.getSensitivities()
    return sum(val for val in self.partialVariances.values())

  def _calcMean(self,fromDict):
    """
    Given a subset, calculate mean from terms
    @ In, fromDict, dict{string:int}, ROM subsets and their multiplicity
    @ Out, tot, float, mean
    """
    tot = 0
    for term,mult in fromDict.items():
      tot += self._evaluateIntegral(term)*mult
    return tot

  def _collectTerms(self,a,targetDict,sign=1,depth=0):
    """
    Adds main term multiplicity and subtracts sub term multiplicity for cross between terms
    @ In, targetDict, dict, dictionary to pace terms in
    @ In, a, string, main combo key from self.terms
    @ In, sign, optional int, gives the signs of the terms (1 for positive, -1 for negative)
    @ In, depth, optional int, recursion depth
    @ Out, None
    """
    if a not in targetDict.keys(): targetDict[a] = sign
    else: targetDict[a] += sign
    for sub in self.terms[a]:
      self._collectTerms(sub,targetDict,sign*-1,depth+1)

  def _evaluateIntegral(self,term):
    """
    Uses properties of orthonormal gPC to algebraically evaluate integrals gPC
    This does assume the integral is over all the constituent variables in the the term
    @ In, term, string, subset term to integrate
    @ Out, float, float, evaluation
    """
    if term in [(),'',None]:
      return self.refSoln
    else:
      return self.ROMs[term].__evaluateMoment__(1)

  def _getANOVATerms(self):
    """
    Converts cut-HDMR into ANOVA terms
    @ In, None
    @ Out, None
    """
    self.raiseADebug('Constructing ANOVA representation...')
    #self.raiseADebug('Reduced terms:')
    #for term,mult in self.reducedTerms.items():
    #  self.raiseADebug(term,self._evaluateIntegral(term),mult)
    #self.raiseADebug('ROMs:')
    #for term in self.reducedTerms.keys():
    #  self.raiseADebug('| Term:',term)
    #  if term == (): continue
    #  for poly,coeff in self.ROMs[term].polyCoeffDict.items():
    #    self.raiseADebug('| | ',poly,coeff)
    #self.raiseADebug('refSoln:',self.refSoln)
    integrals = {}
    for level, combos in enumerate(self.combos):
      #self.combos doesn't include the mean case
      integrals[level] = {}
      if level == 0:
        integrals[level][()] = {():[(self.__mean__(),1,())]}
      for subset in combos:
        integrals[level][subset] = {}
        #integrate out everything but subset
        self._partialIntegrate(self.reducedTerms,subset,integrals[level][subset])
    #subtract off contributing subsets (subsubsets)
    anovaByLevel = {}
    for level in integrals.keys():
      anovaByLevel[level] = {}
      for subset in integrals[level].keys():
        anovaByLevel[level][subset] = dict(integrals[level][subset])
        #subtract subsubset terms
        for sublevel in range(level):
          for subsubset in integrals[sublevel].keys():
            if set(subsubset).issubset(set(subset)):
              for cut,contrib in anovaByLevel[sublevel][subsubset].items():
                #if level == 2 and sublevel == 1:
                if cut not in anovaByLevel[level][subset].keys():
                  anovaByLevel[level][subset][cut] = []
                if type(contrib)==list:
                  for c in contrib:
                    anovaByLevel[level][subset][cut].append( (c[0],c[1]*-1,c[2]) )
                else:
                  anovaByLevel[level][subset][cut].append( (contrib[0],contrib[1]*-1,contrib[2]) )
    #clear mean squared from variance
    del anovaByLevel[0]
    #collect terms of same index set (collect polynomial terms)
    self.raiseADebug('collecting ANOVA terms...')
    self.anova = {}
    for level in anovaByLevel.keys():
      for subset in anovaByLevel[level].keys():
        self.anova[subset] = {} #dictionary of subterms
        for cut,sublist in anovaByLevel[level][subset].items():
          for coeff,mult,idx in sublist:
            fullIdx = self.__fillIndexWithRef(cut,idx)
            if fullIdx not in self.anova[subset].keys():
              #small coeffs already removed
              self.anova[subset][fullIdx] = coeff*mult
            else:
              #if the new sum is zero, clear it
              self.anova[subset][fullIdx] += coeff*mult
              if abs(self.anova[subset][fullIdx]) < 1e-12:
                del self.anova[subset][fullIdx]

  def _partialIntegrate(self,termDict,subset,storeDict):
    """
    Agebraically integrates with respect to all terms except those in subset, using gPC orthogonality
    @ In, termDict, dict{string:int}, terms in integrand and multiplicity
    @ In, subset, tuple(string), subsets not to integrate with respect to
    @ In, storeDict, dict, dict in which results are placed, by term as list[(value,multiplicity,polynomial order tuple)]
    @ Out, None
    """
    # comments will consider the case of integrating f(x,y) dx dy (x,y are integration variables)
    # P_i(s) are orthonormal polynomials of order i with argument s
    # gPC would be given as sum_k c_k P_i(x) P_j(y) with k=(i,j)
    # int( f(x) ) dx indicated integrating f(x) w.r.t. x weighted by the appropriate PDF so that int( 1 ) dx = 1
    debug = False # left for future debug work
    for term,mult in termDict.items():
      wrt = set(set(self.features) - set(subset))
      varInWRT = set(term) & wrt
      if debug: self.raiseADebug('| Integrating',term,'wrt',wrt)
      ### CASE integrating with respect to all of elements in term
      #     for example, int( sum_k c_k P_i(x) P_j(y) ) dx dy = c_(0,0)
      if len(varInWRT) == len(term): #all variables in "term" are integration variables
        if term not in storeDict.keys():
          storeDict[term] = []
        tup = tuple(list(0 for i in range(len(term))))
        storeDict[term].append( (self._evaluateIntegral(term),mult,tup) )
        if debug: self.raiseADebug('|   Expected Value Case:',self._evaluateIntegral(term))
      else:
        for termPoly,coeff in self.ROMs[term].polyCoeffDict.items():
          if debug: self.raiseADebug('|      Integrating poly',termPoly)
          ### CASE coeff is nearly zero, leave it out
          if abs(coeff) < 1e-12: continue #TODO this could result in a speedup, but might not be worth accuracy
          ### CASE any of k_t is nonzero for polynomials of integration variables, then integral is zero
          #     for example, int( sum_k c_k P_i(x) P_j(y) ) dy dz = 0 for every j > 0
          foundNonzeroIntegrated = False
          for var in varInWRT:
            idxInRom = self.ROMs[term].features.index(var)
            if termPoly[idxInRom] > 0:
              foundNonzeroIntegrated = True
              break
          if foundNonzeroIntegrated:
            if debug: self.raiseADebug('|        Nonzero Poly Being Integrated!')
            continue
          ### CASE all the non-zero-order polynomials are with respect to non-integration variables
          #     then after integrating, we have the non-integration polys as a function
          #     for example, int( sum_k c_k P_i(x) P_0(y) ) dy = c_k P_i(x) for every i
          #     BUT since we will be integrating the square of this later, we only store coeff*mult, not the polynomial
          if term not in storeDict.keys():
            storeDict[term] = []
          storeDict[term].append( (coeff,mult,termPoly) )
          if debug: self.raiseADebug('|        Adding functional coeff term:',coeff)

  def _removeZeroTerms(self,d):
    """
    Removes keys from d that have zero value
    @ In, d, dict, string:int
    @ Out, None
    """
    toRemove=[]
    for key,val in d.items():
      if val == 0: toRemove.append(key)
    for rem in toRemove:
      del d[rem]

  def _evaluateSquareIntegral(self,terms):
    """
    Algebraically evaluates the integral of the square of the sum of terms listed in "terms" over the full domain.
    @ In, terms, dict{ tuple(string):list[tuple(float,int,tuple(int))]}, subset:list[tuple(coefficient,multiplicity,source polynomial orders)]}
    @ Out, float, value of integral of square
    """
    #self.raiseADebug('evaluating square integral',color='red')
    #tensor combinations
    tot = 0
    #mult = terms.values()[0][0][2]
    #print('mult:',mult)
    for term in terms.keys():
      pass
    for sourceGPC1,polyTupleList1 in terms.items():
      #self.raiseADebug('| first source:',sourceGPC1,color='red')
      for sourceGPC2,polyTupleList2 in terms.items():
        #self.raiseADebug('| | second source:',sourceGPC2,color='red')
        ### CASE: no overlapping variables, then only keep (0,0,...,0) polynomial coeff
        ### CASE: some overlapping variables, then keep only identical indices
        ### CASE: all overlapping variables, still keep only identical indices
        # any way you look at it, only keep identical indices
        for coeff1,mult1,oidx1 in polyTupleList1:
          idx1 = self.__fillIndexWithRef(sourceGPC1,oidx1)
          #print('A: gPC,mult,idx:',sourceGPC1,mult1,oidx1)
          for coeff2,mult2,oidx2 in polyTupleList2:
            idx2 = self.__fillIndexWithRef(sourceGPC2,oidx2)
            #print('    B: gPC,mult,idx:',sourceGPC2,mult2,oidx2)
            #self.raiseADebug('| | | | coeff2,idx:',coeff2,idx2,color='red')
            #print('| gPC1',sourceGPC1,'idx1',oidx1,'times','gPC2',sourceGPC2,'idx2',oidx2)
            if idx1 == idx2:
              #print('      added to tot:',coeff1*coeff2*mult1*mult2)
              tot += coeff1*coeff2*mult1*mult2
            #else:
            #  self.raiseADebug('|   nothing added.',color='red')
    self.raiseADebug('| Total for terms is',tot,color='red')
    return tot

  def getSensitivities(self):
    """
      Generates dictionary of Sobol indices for the requested levels.
      @ In, None
      @ Out, self.sdx, dict{tuple(str):float}, sensitivity indices
    """
    self.raiseADebug('Calculating sensitivities...')
    maxLevel = max(list(len(combo) for combo in self.ROMs.keys()))
    self._getANOVATerms()
    # calculate partial variance contribution of each term in ANOVA
    self.sdx = {}
    self.partialVariances = {}
    # need to consider all combinations of terms within each term
    for subset in self.anova.keys():
      self.partialVariances[subset] = sum(c*c for c in self.anova[subset].values())

  def getPercentSensitivities(self,variance=None,returnTotal=False):
    """Calculates percent sensitivities.
    If variance specified, uses it as the bnechmark variance, otherwise uses ROM to calculate total variance approximately.
    If returnTotal specified, also returns percent of total variance and the total variance value.
    FIXME these are not Sobol sensitivity indices!  This can't be done this way with cut-HDMR.
    @ In, variance, float to represent user-provided total variance
    @ In, returnTotal, boolean to turn on returning total percent and total variance
    @ Out, pcts, percent=based Sobol sensitivity indices
    """
    if self.partialVariances == None or len(self.partialVariances)<1:
      self.getSensitivities()
    sumVar = 0.0
    for subset,partialVariance in self.partialVariances.items():
      sumVar += partialVariance
    tot=0.0
    self.sdx={}
    for subset,partialVariance in self.partialVariances.items():
      if subset == (): continue
      self.sdx[subset]=partialVariance/sumVar
      tot+=self.sdx[subset]
    #DEBUG
    self.raiseADebug('percent sensitivities')
    self.raiseADebug('  ANOVA summed variance:',sumVar)
    self.raiseADebug('  Subset, Partial Variance, Percent Variance:')
    for subset in self.sdx.keys():
      self.raiseADebug('   ',subset,self.partialVariances[subset],self.sdx[subset])
    self.raiseADebug('  total percent variance  :',tot)
    #END DEBUG
    if returnTotal: return self.sdx,tot,sumVar
    else: return self.sdx

#
#
#
#
class MSR(NDinterpolatorRom):
  """
    MSR class - Computes an approximated hierarchical Morse-Smale decomposition
    from an input point cloud consisting of an arbitrary number of input
    parameters and one or more response values per input point
  """
  def __init__(self, messageHandler, **kwargs):
    """
     Constructor that will appropriately initialize an MSR object
    @In, messageHandler, MessageHandler, in charge of raising errors and
         printing messages
    @In, kwargs, dict, an arbitrary dictionary of keywords and values
    """
    self.printTag = 'MSR ROM'
    superVisedLearning.__init__(self,messageHandler,**kwargs)
    self.acceptedGraphParam = ['approximate knn', 'delaunay', 'beta skeleton', \
                               'relaxed beta skeleton']
    self.acceptedPersistenceParam = ['difference','probability','count','area']
    self.acceptedGradientParam = ['steepest', 'maxflow']
    self.acceptedNormalizationParam = ['feature', 'zscore', 'none']
    self.acceptedPredictorParam = ['kde', 'svm']
    self.acceptedKernelParam = ['uniform', 'triangular', 'epanechnikov',
                                'biweight', 'quartic', 'triweight', 'tricube',
                                'gaussian', 'cosine', 'logistic', 'silverman',
                                'exponential']

    # Some sensible default arguments
    self.gradient = 'steepest'            # Gradient estimate methodology
    self.graph = 'beta skeleton'          # Neighborhood graph used
    self.beta = 1                         # beta used in the beta skeleton graph
                                          #  and its relaxed version
    self.knn = -1                         # k-nearest neighbor value for either
                                          #  the approximate knn strategy, or
                                          #  for initially pruning the beta
                                          #  skeleton graphs. (this could also
                                          #  potentially be used for restricting
                                          #  the models influencing a query
                                          #  point to only use those models
                                          #  belonging to a limited
                                          #  neighborhood of training points)
    self.simplification = 0               # Morse-smale simplification amount
                                          #  this should probably be normalized
                                          #  to [0,1], however for now it is not
                                          #  and the scale of it will depend on
                                          #  the type of persistence used
    self.persistence = 'difference'       # Strategy for merging topo partitions
    self.weighted = False                 # Should the linear models be weighted
                                          #  by probability information?
    self.normalization = None             # Should any normalization be
                                          #  performed within the AMSC? No, this
                                          #  data should already be standardized
    self.partitionPredictor = 'kde'       # The method used to predict the label
                                          #  of each query point (can be soft).
    self.blending = False                 # Flag: blend the predictions
                                          #  depending on soft label predictions
                                          #  or use only the most likely local
                                          #  model
    self.kernel = 'gaussian'              # What kernel should be used in the
                                          #  kde approach
    self.bandwidth = 1.                   # The bandwidth for the kde approach

    # Read everything in first, and then do error checking as some parameters
    # will not matter, but we can still throw a warning message that they may
    # want to clean up there input file. In some cases, we will have to do
    # value checking in place since the type cast can fail.
    for key,val in kwargs.items():
      if key.lower() == 'graph':
        self.graph = val.strip().encode('ascii').lower()
      elif key.lower() == "gradient":
        self.gradient = val.strip().encode('ascii').lower()
      elif key.lower() == "beta":
        try:
          self.beta = float(val)
        except ValueError:
          # If the user has specified a graph, use it, otherwise be sure to use
          #  the default when checking whether this is a warning or an error
          if 'graph' in kwargs:
            graph = kwargs['graph'].strip().encode('ascii').lower()
          else:
            graph = self.graph
          if graph.endswith('beta skeleton'):
            self.raiseAnError(IOError, 'Requested invalid beta value:',
                              val, '(Allowable range: (0,2])')
          else:
            self.raiseAWarning('Requested invalid beta value:', self.beta,
                               '(Allowable range: (0,2]), however beta is',
                               'ignored when using the', graph,
                               'graph structure.')
      elif key.lower() == 'knn':
        try:
          self.knn = int(val)
        except ValueError:
          self.raiseAnError(IOError, 'Requested invalid knn value:',
                            val, '(Should be an integer value, knn <= 0 implies'
                            ,'use of the fully connected point set)')
      elif key.lower() == 'simplification':
        try:
          self.simplification = float(val)
        except ValueError:
          self.raiseAnError(IOError, 'Requested invalid simplification level:',
                            val, '(should be a floating point value)')
      elif key.lower() == 'bandwidth':
        if val == 'variable' or val == 'auto':
          self.bandwidth = val
        else:
          try:
            self.bandwidth = float(val)
          except ValueError:
            # If the user has specified a strategy, use it, otherwise be sure to
            #  use the default when checking whether this is a warning or an error
            if 'partitionPredictor' in kwargs:
              partPredictor = kwargs['partitionPredictor'].strip().encode('ascii').lower()
            else:
              partPredictor = self.partitionPredictor
            if partPredictor == 'kde':
              self.raiseAnError(IOError, 'Requested invalid bandwidth value:',
                                val,'(should be a positive floating point value)')
            else:
              self.raiseAWarning('Requested invalid bandwidth value:',val,
                                 '(bandwidth > 0 or \"variable\"). However, it is ignored when',
                                 'using the', partPredictor, 'partition',
                                 'predictor')
      elif key.lower() == 'persistence':
        self.persistence = val.strip().encode('ascii').lower()
      elif key.lower() == 'partitionpredictor':
        self.partitionPredictor = val.strip().encode('ascii').lower()
      elif key.lower() == 'smooth':
        self.blending = True
      elif key.lower() == "kernel":
        self.kernel = val
      else:
        pass

    # Morse-Smale specific error handling
    if self.graph not in self.acceptedGraphParam:
      self.raiseAnError(IOError, 'Requested unknown graph type:',
                        '\"'+self.graph+'\"','(Available options:',
                        self.acceptedGraphParam,')')
    if self.gradient not in self.acceptedGradientParam:
      self.raiseAnError(IOError, 'Requested unknown gradient method:',
                        '\"'+self.gradient+'\"', '(Available options:',
                        self.acceptedGradientParam,')')
    if self.beta <= 0 or self.beta > 2:
      if self.graph.endswith('beta skeleton'):
        self.raiseAnError(IOError, 'Requested invalid beta value:',
                          self.beta, '(Allowable range: (0,2])')
      else:
        self.raiseAWarning('Requested invalid beta value:', self.beta,
                           '(Allowable range: (0,2]), however beta is',
                           'ignored when using the', self.graph,
                           'graph structure.')
    if self.persistence not in self.acceptedPersistenceParam:
      self.raiseAnError(IOError, 'Requested unknown persistence method:',
                        '\"'+self.persistence+'\"', '(Available options:',
                        self.acceptedPersistenceParam,')')
    if self.partitionPredictor not in self.acceptedPredictorParam:
      self.raiseAnError(IOError, 'Requested unknown partition predictor:'
                        '\"'+self.partitionPredictor+'\"','(Available options:',
                        self.acceptedPredictorParam,')')
    if self.bandwidth <= 0:
      if self.partitionPredictor == 'kde':
        self.raiseAnError(IOError, 'Requested invalid bandwidth value:',
                          self.bandwidth, '(bandwidth > 0)')
      else:
        self.raiseAWarning(IOError, 'Requested invalid bandwidth value:',
                          self.bandwidth, '(bandwidth > 0). However, it is',
                          'ignored when using the', self.partitionPredictor,
                          'partition predictor')

    if self.kernel not in self.acceptedKernelParam:
      if self.partitionPredictor == 'kde':
        self.raiseAnError(IOError, 'Requested unknown kernel:',
                          '\"'+self.kernel+'\"', '(Available options:',
                          self.acceptedKernelParam,')')
      else:
        self.raiseAWarning('Requested unknown kernel:', '\"'+self.kernel+'\"',
                           '(Available options:', self.acceptedKernelParam,
                           '), however the kernel is ignored when using the',
                           self.partitionPredictor,'partition predictor.')
    self.__resetLocal__()

  def __getstate__(self):
    state = dict(self.__dict__)
    state.pop('_MSR__amsc')
    state.pop('kdTree')
    return state

  def __setstate__(self,newState):
    for key, value in newState.iteritems():
        setattr(self, key, value)
    self.kdTree             = None
    self.__amsc             = None
    self.__trainLocal__(self.X,self.Y)

  def __trainLocal__(self,featureVals,targetVals):
    """
    Perform training on samples in featureVals with responses y.

    @In, featureVals, {array-like, sparse matrix}, shape=[n_samples, n_features],
      an array of input feature values
    @ Out, targetVals, array, shape = [n_samples], an array of output target
      associated with the corresponding points in featureVals
    """

    # # Possibly load this here in case people have trouble building it, so it
    # # only errors if they try to use it?
    from AMSC_Object import AMSC_Object

    self.X = featureVals[:][:]
    self.Y = targetVals

    if self.weighted:
      self.raiseAnError(NotImplementedError,
                    ' cannot use weighted data right now.')
    else:
      weights = None

    if self.knn <= 0:
      self.knn = self.X.shape[0]

    names = [name.encode('ascii') for name in self.features + [self.target]]
    # Data is already normalized, so ignore this parameter
    ### Comment replicated from the post-processor version, not sure what it
    ### means (DM)
    # FIXME: AMSC_Object employs unsupervised NearestNeighbors algorithm from
    #        scikit learn.
    #        The NearestNeighbor algorithm is implemented in
    #        SupervisedLearning, which requires features and targets by
    #        default, which we don't have here. When the NearestNeighbor is
    #        implemented in unSupervisedLearning switch to it.
    self.__amsc = AMSC_Object(X=self.X, Y=self.Y, w=weights, names=names,
                              graph=self.graph, gradient=self.gradient,
                              knn=self.knn, beta=self.beta,
                              normalization=None,
                              persistence=self.persistence)
    self.__amsc.Persistence(self.simplification)
    self.__amsc.BuildLinearModels(self.simplification)

    # We need a KD-Tree for querying neighbors
    self.kdTree = neighbors.KDTree(self.X)

    distances,_ = self.kdTree.query(self.X,k=self.knn)
    distances = distances.flatten()

    # The following are a list of common kernels defined centered at zero with
    # either infinite support or a support defined over the interval [1,1].
    # See: https://en.wikipedia.org/wiki/Kernel_(statistics)
    # Thus, the use of this indicator function. When using these kernels, we
    # must be sure to first scale the parameter into this support before calling
    # it. In our case, we want to center our information, such that the maximum
    # value occurs when the two points coincide, and so we will set u to be
    # inversely proportional to the distance between two points, and scaled by
    # a bandwidth parameter (either the user will fix, or we will compute)
    def indicator(u):
      return np.abs(u)<1

    if self.kernel == 'uniform':
      if self.bandwidth == 'auto':
        self.bandwidth = max(distances)
        self.raiseAWarning('automatic bandwidth not yet implemented for the'
                           + self.kernel + ' kernel.')
      def kernel(u):
        return 0.5*indicator(u)
    elif self.kernel == 'triangular':
      if self.bandwidth == 'auto':
        self.bandwidth = max(distances)
        self.raiseAWarning('automatic bandwidth not yet implemented for the'
                           + self.kernel + ' kernel.')
      def kernel(u):
        return (1-abs(u))*indicator(u)
    elif self.kernel == 'epanechnikov':
      if self.bandwidth == 'auto':
        self.bandwidth = max(distances)
        self.raiseAWarning('automatic bandwidth not yet implemented for the'
                           + self.kernel + ' kernel.')
      def kernel(u):
        return ( 3./4. )*(1-u**2)*indicator(u)
    elif self.kernel == 'biweight' or self.kernel == 'quartic':
      if self.bandwidth == 'auto':
        self.bandwidth = max(distances)
        self.raiseAWarning('automatic bandwidth not yet implemented for the'
                           + self.kernel + ' kernel.')
      def kernel(u):
        return (15./16.)*(1-u**2)**2*indicator(u)
    elif self.kernel == 'triweight':
      if self.bandwidth == 'auto':
        self.bandwidth = max(distances)
        self.raiseAWarning('automatic bandwidth not yet implemented for the'
                           + self.kernel + ' kernel.')
      def kernel(u):
        return (35./32.)*(1-u**2)**3*indicator(u)
    elif self.kernel == 'tricube':
      if self.bandwidth == 'auto':
        self.bandwidth = max(distances)
        self.raiseAWarning('automatic bandwidth not yet implemented for the'
                           + self.kernel + ' kernel.')
      def kernel(u):
        return (70./81.)*(1-abs(u)**3)**3*indicator(u)
    elif self.kernel == 'gaussian':
      if self.bandwidth == 'auto':
        self.bandwidth = 1.06*distances.std()*len(distances)**(-1./5.)
        self.raiseAWarning('automatic bandwidth not yet implemented for the'
                           + self.kernel + ' kernel.')
      def kernel(u):
        return 1./np.sqrt(2*math.pi)*np.exp(-0.5*u**2)
    elif self.kernel == 'cosine':
      if self.bandwidth == 'auto':
        self.bandwidth = max(distances)
        self.raiseAWarning('automatic bandwidth not yet implemented for the'
                           + self.kernel + ' kernel.')
      def kernel(u):
        return math.pi/4.*math.cos(u*math.pi/2.)*indicator(u)
    elif self.kernel == 'logistic':
      if self.bandwidth == 'auto':
        self.bandwidth = max(distances)
        self.raiseAWarning('automatic bandwidth not yet implemented for the'
                           + self.kernel + ' kernel.')
      def kernel(u):
        return 1./(np.exp(u)+2+np.exp(-u))
    elif self.kernel == 'silverman':
      if self.bandwidth == 'auto':
        self.bandwidth = max(distances)
        self.raiseAWarning('automatic bandwidth not yet implemented for the'
                           + self.kernel + ' kernel.')
      def kernel(u):
        sqrt2 = math.sqrt(2)
        return 0.5 * np.exp(-abs(u)/sqrt2) * np.sin(abs(u)/sqrt2+math.pi/4.)
    elif self.kernel == 'exponential':
      if self.bandwidth == 'auto':
        self.bandwidth = max(distances)
        self.raiseAWarning('automatic bandwidth not yet implemented for the'
                           + self.kernel + ' kernel.')
      def kernel(u):
        return np.exp(-abs(u))
    self.__kernel = kernel

  def __confidenceLocal__(self,featureVals):
    """
    This should return an estimation of the quality of the prediction.
    Should return distance to nearest neighbor or average prediction error of
    all neighbors?
    @ In, featureVals, 2-D numpy array [n_samples,n_features]
    @ Out, float, the confidence
    """
    self.raiseAnError(NotImplementedError,
                      '__confidenceLocal__ method must be implemented!')

  def __evaluateLocal__(self,featureVals):
    """
    Perform regression on samples in featureVals.
    This will use the local predictor of each neighboring point weighted by its
    distance to that point.
    @ In, numpy.array 2-D, features
    @ Out, numpy.array 1-D, predicted values
    """
    if self.partitionPredictor == 'kde':
      partitions = self.__amsc.Partitions(self.simplification)
      weights = {}
      dists = np.zeros((featureVals.shape[0],self.X.shape[0]))
      for i,row in enumerate(featureVals):
        dists[i] = np.sqrt(((row-self.X)**2).sum(axis=-1))
      # This is a variable-based bandwidth that will adjust to the density
      # around the given query point
      if self.bandwidth == 'variable':
        h = sorted(dists)[self.knn-1]
      else:
        h = self.bandwidth
      for key,indices in partitions.iteritems():
        #############
        ## Using SciKit Learn, we have a limited number of kernel functions to
        ## choose from.
        # kernel = self.kernel
        # if kernel == 'uniform':
        #   kernel = 'tophat'
        # if kernel == 'triangular':
        #   kernel = 'linear'
        # kde = KernelDensity(kernel=kernel, bandwidth=h).fit(self.X[indices,])
        # weights[key] = np.exp(kde.score_samples(featureVals))
        #############
        ## OR
        #############
        weights[key] = 0
        for idx in indices:
          weights[key] += self.__kernel(dists[:,idx]/h)
        weights[key]
        #############

      if self.blending:
        weightedPredictions = np.zeros(featureVals.shape[0])
        sumW = 0
        for key in partitions.keys():
          fx = self.__amsc.Predict(featureVals,key)
          wx = weights[key]
          sumW += wx
          weightedPredictions += fx*wx
        if sumW == 0:
          return weightedPredictions
        return weightedPredictions / sumW
      else:
        predictions = np.zeros(featureVals.shape[0])
        maxWeights = np.zeros(featureVals.shape[0])
        for key in partitions.keys():
          fx = self.__amsc.Predict(featureVals,key)
          wx = weights[key]
          predictions[wx > maxWeights] = fx
          maxWeights[wx > maxWeights] = wx
        return predictions
    elif self.partitionPredictor == 'svm':
      partitions = self.__amsc.Partitions(self.simplification)
      labels = np.zeros(self.X.shape[0])
      for idx,(key,indices) in enumerate(partitions.iteritems()):
        labels[np.array(indices)] = idx
      # In order to make this deterministic for testing purposes, let's fix
      # the random state of the SVM object. Maybe, this could be exposed to the
      # user, but it shouldn't matter too much what the seed is for this.
      svc = svm.SVC(probability=True,random_state=np.random.RandomState(8),tol=1e-15)
      svc.fit(self.X,labels)
      probabilities = svc.predict_proba(featureVals)

      classIdxs = list(svc.classes_)
      if self.blending:
        weightedPredictions = np.zeros(len(featureVals))
        sumW = 0
        for idx,key in enumerate(partitions.keys()):
          fx = self.__amsc.Predict(featureVals,key)
          # It could be that a particular partition consists of only the extrema
          # and they themselves point to cells with different opposing extrema.
          # That is, a maximum points to a different minimum than the minimum in
          # the two point partition. Long story short, we need to be prepared for
          # an empty partition which will thus not show up in the predictions of
          # the SVC, since no point has it as a label.
          if idx not in classIdxs:
            wx = np.zeros(probabilities.shape[0])
          else:
            realIdx = list(svc.classes_).index(idx)
            wx = probabilities[:,realIdx]
          if self.blending:
            weightedPredictions = weightedPredictions + fx*wx
            sumW += wx

        return weightedPredictions/sumW
      else:
        predictions = np.zeros(featureVals.shape[0])
        maxWeights = np.zeros(featureVals.shape[0])
        for idx,key in enumerate(partitions.keys()):
          fx = self.__amsc.Predict(featureVals,key)
          # It could be that a particular partition consists of only the extrema
          # and they themselves point to cells with different opposing extrema.
          # That is, a maximum points to a different minimum than the minimum in
          # the two point partition. Long story short, we need to be prepared for
          # an empty partition which will thus not show up in the predictions of
          # the SVC, since no point has it as a label.
          if idx not in classIdxs:
            wx = np.zeros(probabilities.shape[0])
          else:
            realIdx = list(svc.classes_).index(idx)
            wx = probabilities[:,realIdx]
          predictions[wx > maxWeights] = fx
          maxWeights[wx > maxWeights] = wx

        return predictions


  def __resetLocal__(self):
    """
    The reset here will erase the internal data while keeping the
    instance
    """
    self.X      = []
    self.Y      = []
    self.__amsc = None
    self.kdTree = None


#
#
#
class NDsplineRom(NDinterpolatorRom):
  """
  An N-dimensional Spline model
  """
  ROMtype         = 'NDsplineRom'
  def __init__(self,messageHandler,**kwargs):
    """
    A constructor that will appropriately intialize a supervised learning object
    @In, messageHandler: a MessageHandler object in charge of raising errors,
                         and printing messages
    @In, kwargs: an arbitrary dictionary of keywords and values
    """
    NDinterpolatorRom.__init__(self,messageHandler,**kwargs)
    self.printTag = 'ND-SPLINE ROM'
    self.interpolator = interpolationND.NDspline()

  def __resetLocal__(self):
    """ The reset here erase the Interpolator while keeping the instance"""
    self.interpolator.reset()
#
#
#
class NDinvDistWeight(NDinterpolatorRom):
  """
  An N-dimensional model that interpolates data based on a inverse weighting of
  their training data points?
  """
  ROMtype         = 'NDinvDistWeight'
  def __init__(self,messageHandler,**kwargs):
    """
    A constructor that will appropriately intialize a supervised learning object
    @In, messageHandler: a MessageHandler object in charge of raising errors,
                         and printing messages
    @In, kwargs: an arbitrary dictionary of keywords and values
    """
    NDinterpolatorRom.__init__(self,messageHandler,**kwargs)
    self.printTag = 'ND-INVERSEWEIGHT ROM'
    if not 'p' in self.initOptionDict.keys(): self.raiseAnError(IOError,'the <p> parameter must be provided in order to use NDinvDistWeigth as ROM!!!!')
    self.__initLocal__()

  def __initLocal__(self):
    self.interpolator = interpolationND.InverseDistanceWeighting(float(self.initOptionDict['p']))

  def __resetLocal__(self):
    """ The reset here erase the Interpolator while keeping the instance"""
    self.interpolator.reset(float(self.initOptionDict['p']))
#
#
#
class SciKitLearn(superVisedLearning):
  """
  An Interface to the ROMs provided by skLearn
  """
  ROMtype = 'SciKitLearn'
  availImpl = {}
  availImpl['lda'] = {}
  availImpl['lda']['LDA'] = (lda.LDA, 'integer') #Quadratic Discriminant Analysis (QDA)
  availImpl['linear_model'] = {} #Generalized Linear Models
  availImpl['linear_model']['ARDRegression'               ] = (linear_model.ARDRegression               , 'float'  ) #Bayesian ARD regression.
  availImpl['linear_model']['BayesianRidge'               ] = (linear_model.BayesianRidge               , 'float'  ) #Bayesian ridge regression
  availImpl['linear_model']['ElasticNet'                  ] = (linear_model.ElasticNet                  , 'float'  ) #Linear Model trained with L1 and L2 prior as regularizer
  availImpl['linear_model']['ElasticNetCV'                ] = (linear_model.ElasticNetCV                , 'float'  ) #Elastic Net model with iterative fitting along a regularization path
  availImpl['linear_model']['Lars'                        ] = (linear_model.Lars                        , 'float'  ) #Least Angle Regression model a.k.a.
  availImpl['linear_model']['LarsCV'                      ] = (linear_model.LarsCV                      , 'float'  ) #Cross-validated Least Angle Regression model
  availImpl['linear_model']['Lasso'                       ] = (linear_model.Lasso                       , 'float'  ) #Linear Model trained with L1 prior as regularizer (aka the Lasso)
  availImpl['linear_model']['LassoCV'                     ] = (linear_model.LassoCV                     , 'float'  ) #Lasso linear model with iterative fitting along a regularization path
  availImpl['linear_model']['LassoLars'                   ] = (linear_model.LassoLars                   , 'float'  ) #Lasso model fit with Least Angle Regression a.k.a.
  availImpl['linear_model']['LassoLarsCV'                 ] = (linear_model.LassoLarsCV                 , 'float'  ) #Cross-validated Lasso, using the LARS algorithm
  availImpl['linear_model']['LassoLarsIC'                 ] = (linear_model.LassoLarsIC                 , 'float'  ) #Lasso model fit with Lars using BIC or AIC for model selection
  availImpl['linear_model']['LinearRegression'            ] = (linear_model.LinearRegression            , 'float'  ) #Ordinary least squares Linear Regression.
  availImpl['linear_model']['LogisticRegression'          ] = (linear_model.LogisticRegression          , 'float'  ) #Logistic Regression (aka logit, MaxEnt) classifier.
  availImpl['linear_model']['MultiTaskLasso'              ] = (linear_model.MultiTaskLasso              , 'float'  ) #Multi-task Lasso model trained with L1/L2 mixed-norm as regularizer
  availImpl['linear_model']['MultiTaskElasticNet'         ] = (linear_model.MultiTaskElasticNet         , 'float'  ) #Multi-task ElasticNet model trained with L1/L2 mixed-norm as regularizer
  availImpl['linear_model']['OrthogonalMatchingPursuit'   ] = (linear_model.OrthogonalMatchingPursuit   , 'float'  ) #Orthogonal Mathching Pursuit model (OMP)
  availImpl['linear_model']['OrthogonalMatchingPursuitCV' ] = (linear_model.OrthogonalMatchingPursuitCV , 'float'  ) #Cross-validated Orthogonal Mathching Pursuit model (OMP)
  availImpl['linear_model']['PassiveAggressiveClassifier' ] = (linear_model.PassiveAggressiveClassifier , 'integer') #Passive Aggressive Classifier
  availImpl['linear_model']['PassiveAggressiveRegressor'  ] = (linear_model.PassiveAggressiveRegressor  , 'float'  ) #Passive Aggressive Regressor
  availImpl['linear_model']['Perceptron'                  ] = (linear_model.Perceptron                  , 'float'  ) #Perceptron
  availImpl['linear_model']['RandomizedLasso'             ] = (linear_model.RandomizedLasso             , 'float'  ) #Randomized Lasso.
  availImpl['linear_model']['RandomizedLogisticRegression'] = (linear_model.RandomizedLogisticRegression, 'float'  ) #Randomized Logistic Regression
  availImpl['linear_model']['Ridge'                       ] = (linear_model.Ridge                       , 'float'  ) #Linear least squares with l2 regularization.
  availImpl['linear_model']['RidgeClassifier'             ] = (linear_model.RidgeClassifier             , 'float'  ) #Classifier using Ridge regression.
  availImpl['linear_model']['RidgeClassifierCV'           ] = (linear_model.RidgeClassifierCV           , 'integer') #Ridge classifier with built-in cross-validation.
  availImpl['linear_model']['RidgeCV'                     ] = (linear_model.RidgeCV                     , 'float'  ) #Ridge regression with built-in cross-validation.
  availImpl['linear_model']['SGDClassifier'               ] = (linear_model.SGDClassifier               , 'integer') #Linear classifiers (SVM, logistic regression, a.o.) with SGD training.
  availImpl['linear_model']['SGDRegressor'                ] = (linear_model.SGDRegressor                , 'float'  ) #Linear model fitted by minimizing a regularized empirical loss with SGD
  availImpl['linear_model']['lars_path'                   ] = (linear_model.lars_path                   , 'float'  ) #Compute Least Angle Regression or Lasso path using LARS algorithm [1]
  availImpl['linear_model']['lasso_path'                  ] = (linear_model.lasso_path                  , 'float'  ) #Compute Lasso path with coordinate descent
  availImpl['linear_model']['lasso_stability_path'        ] = (linear_model.lasso_stability_path        , 'float'  ) #Stabiliy path based on randomized Lasso estimates
  availImpl['linear_model']['orthogonal_mp_gram'          ] = (linear_model.orthogonal_mp_gram          , 'float'  ) #Gram Orthogonal Matching Pursuit (OMP)

  availImpl['svm'] = {} #support Vector Machines
  availImpl['svm']['LinearSVC'] = (svm.LinearSVC, 'boolean')
  availImpl['svm']['SVC'      ] = (svm.SVC      , 'boolean')
  availImpl['svm']['NuSVC'    ] = (svm.NuSVC    , 'boolean')
  availImpl['svm']['SVR'      ] = (svm.SVR      , 'boolean')

  availImpl['multiClass'] = {} #Multiclass and multilabel classification
  availImpl['multiClass']['OneVsRestClassifier' ] = (multiclass.OneVsRestClassifier , 'integer') # One-vs-the-rest (OvR) multiclass/multilabel strategy
  availImpl['multiClass']['OneVsOneClassifier'  ] = (multiclass.OneVsOneClassifier  , 'integer') # One-vs-one multiclass strategy
  availImpl['multiClass']['OutputCodeClassifier'] = (multiclass.OutputCodeClassifier, 'integer') # (Error-Correcting) Output-Code multiclass strategy
  availImpl['multiClass']['fit_ovr'             ] = (multiclass.fit_ovr             , 'integer') # Fit a one-vs-the-rest strategy.
  availImpl['multiClass']['predict_ovr'         ] = (multiclass.predict_ovr         , 'integer') # Make predictions using the one-vs-the-rest strategy.
  availImpl['multiClass']['fit_ovo'             ] = (multiclass.fit_ovo             , 'integer') # Fit a one-vs-one strategy.
  availImpl['multiClass']['predict_ovo'         ] = (multiclass.predict_ovo         , 'integer') # Make predictions using the one-vs-one strategy.
  availImpl['multiClass']['fit_ecoc'            ] = (multiclass.fit_ecoc            , 'integer') # Fit an error-correcting output-code strategy.
  availImpl['multiClass']['predict_ecoc'        ] = (multiclass.predict_ecoc        , 'integer') # Make predictions using the error-correcting output-code strategy.

  availImpl['naiveBayes'] = {}
  availImpl['naiveBayes']['GaussianNB'   ] = (naive_bayes.GaussianNB   , 'float')
  availImpl['naiveBayes']['MultinomialNB'] = (naive_bayes.MultinomialNB, 'float')
  availImpl['naiveBayes']['BernoulliNB'  ] = (naive_bayes.BernoulliNB  , 'float')

  availImpl['neighbors'] = {}
  availImpl['neighbors']['NearestNeighbors']         = (neighbors.NearestNeighbors         , 'float'  )# Unsupervised learner for implementing neighbor searches.
  availImpl['neighbors']['KNeighborsClassifier']     = (neighbors.KNeighborsClassifier     , 'integer')# Classifier implementing the k-nearest neighbors vote.
  availImpl['neighbors']['RadiusNeighbors']          = (neighbors.RadiusNeighborsClassifier, 'integer')# Classifier implementing a vote among neighbors within a given radius
  availImpl['neighbors']['KNeighborsRegressor']      = (neighbors.KNeighborsRegressor      , 'float'  )# Regression based on k-nearest neighbors.
  availImpl['neighbors']['RadiusNeighborsRegressor'] = (neighbors.RadiusNeighborsRegressor , 'float'  )# Regression based on neighbors within a fixed radius.
  availImpl['neighbors']['NearestCentroid']          = (neighbors.NearestCentroid          , 'integer')# Nearest centroid classifier.
  availImpl['neighbors']['BallTree']                 = (neighbors.BallTree                 , 'float'  )# BallTree for fast generalized N-point problems
  availImpl['neighbors']['KDTree']                   = (neighbors.KDTree                   , 'float'  )# KDTree for fast generalized N-point problems

  availImpl['qda'] = {}
  availImpl['qda']['QDA'] = (qda.QDA, 'integer') #Quadratic Discriminant Analysis (QDA)

  availImpl['tree'] = {}
  availImpl['tree']['DecisionTreeClassifier'] = (tree.DecisionTreeClassifier, 'integer')# A decision tree classifier.
  availImpl['tree']['DecisionTreeRegressor' ] = (tree.DecisionTreeRegressor , 'float'  )# A tree regressor.
  availImpl['tree']['ExtraTreeClassifier'   ] = (tree.ExtraTreeClassifier   , 'integer')# An extremely randomized tree classifier.
  availImpl['tree']['ExtraTreeRegressor'    ] = (tree.ExtraTreeRegressor    , 'float'  )# An extremely randomized tree regressor.

  availImpl['GaussianProcess'] = {}
  availImpl['GaussianProcess']['GaussianProcess'] = (gaussian_process.GaussianProcess    , 'float'  )
  #test if a method to estimate the probability of the prediction is available
  qualityEstTypeDict = {}
  for key1, myDict in availImpl.items():
    qualityEstTypeDict[key1] = {}
    for key2 in myDict:
      qualityEstTypeDict[key1][key2] = []
      if  callable(getattr(myDict[key2][0], "predict_proba", None))  : qualityEstTypeDict[key1][key2] += ['probability']
      elif  callable(getattr(myDict[key2][0], "score"        , None)): qualityEstTypeDict[key1][key2] += ['score']
      else                                                           : qualityEstTypeDict[key1][key2] = False

  def __init__(self,messageHandler,**kwargs):
    """
    A constructor that will appropriately intialize a supervised learning object
    @In, messageHandler: a MessageHandler object in charge of raising errors,
                         and printing messages
    @In, kwargs: an arbitrary dictionary of keywords and values
    """
    superVisedLearning.__init__(self,messageHandler,**kwargs)
    self.printTag = 'SCIKITLEARN'
    if 'SKLtype' not in self.initOptionDict.keys(): self.raiseAnError(IOError,'to define a scikit learn ROM the SKLtype keyword is needed (from ROM '+self.name+')')
    SKLtype, SKLsubType = self.initOptionDict['SKLtype'].split('|')
    self.initOptionDict.pop('SKLtype')
    if not SKLtype in self.__class__.availImpl.keys(): self.raiseAnError(IOError,'not known SKLtype ' + SKLtype +'(from ROM '+self.name+')')
    if not SKLsubType in self.__class__.availImpl[SKLtype].keys(): self.raiseAnError(IOError,'not known SKLsubType ' + SKLsubType +'(from ROM '+self.name+')')
    self.__class__.returnType     = self.__class__.availImpl[SKLtype][SKLsubType][1]
    self.ROM                      = self.__class__.availImpl[SKLtype][SKLsubType][0]()
    self.__class__.qualityEstType = self.__class__.qualityEstTypeDict[SKLtype][SKLsubType]
    for key,value in self.initOptionDict.items():
      try:self.initOptionDict[key] = ast.literal_eval(value)
      except: pass
    self.ROM.set_params(**self.initOptionDict)

  def _readdressEvaluateConstResponse(self,edict):
    """
    Method to re-address the evaluate base class method in order to avoid wasting time
    in case the training set has an unique response (e.g. if 10 points in the training set,
    and the 10 outcomes are all == to 1, this method returns one without the need of an
    evaluation)
    @ In, prediction request, Not used in this method (kept the consistency with evaluate method)
    """
    return self.myNumber

  def _readdressEvaluateRomResponse(self,edict):
    """
    Method to re-address the evaluate base class method to its original method
    @ In, prediction request, used in this method (kept the consistency with evaluate method)
    """
    return self.__class__.evaluate(self,edict)

  def __trainLocal__(self,featureVals,targetVals):
    """
    Perform training on samples in featureVals with responses y.
    For an one-class model, +1 or -1 is returned.

    @In, featureVals, {array-like, sparse matrix}, shape=[n_samples, n_features],
      an array of input feature values
    @ Out, targetVals, array, shape = [n_samples], an array of output target
      associated with the corresponding points in featureVals
    """
    #If all the target values are the same no training is needed and the moreover the self.evaluate could be re-addressed to this value
    if len(np.unique(targetVals))>1:
      self.ROM.fit(featureVals,targetVals)
      self.evaluate = self._readdressEvaluateRomResponse
      #self.evaluate = lambda edict : self.__class__.evaluate(self,edict)
    else:
      self.myNumber = np.unique(targetVals)[0]
      self.evaluate = self._readdressEvaluateConstResponse

  def __confidenceLocal__(self,edict):
    """
    This should return an estimation of the quality of the prediction.
    @ In, featureVals, 2-D numpy array [n_samples,n_features]
    @ Out, float, the confidence
    """
    if  'probability' in self.__class__.qualityEstType: return self.ROM.predict_proba(edict)
    else            : self.raiseAnError(IOError,'the ROM '+str(self.name)+'has not the an method to evaluate the confidence of the prediction')

  def __evaluateLocal__(self,featureVals):
    """ Evaluates a point.
    @ In, featureVals, list of values at which to evaluate the ROM
    @ Out, float, the evaluated value
    """
    return self.ROM.predict(featureVals)

  def __resetLocal__(self):
    """
    After this method the ROM should be described only by the initial
    parameter settings
    @In None
    @ Out None
    """
    self.ROM = self.ROM.__class__(**self.initOptionDict)

  def __returnInitialParametersLocal__(self):
    """
    Returns a dictionary with the parameters and their initial values
    @In None
    @ Out dictionary of parameter names and initial values
    """
    return self.ROM.get_params()

  def __returnCurrentSettingLocal__(self):
    """
    Returns a dictionary with the parameters and their current values
    @In None
    @ Out dictionary of parameter names and current values
    """
    self.raiseADebug('here we need to collect some info on the ROM status')
    localInitParam = {}
    return localInitParam
#
#
#
__interfaceDict                         = {}
__interfaceDict['NDspline'            ] = NDsplineRom
__interfaceDict['NDinvDistWeight'     ] = NDinvDistWeight
__interfaceDict['SciKitLearn'         ] = SciKitLearn
__interfaceDict['GaussPolynomialRom'  ] = GaussPolynomialRom
__interfaceDict['HDMRRom'             ] = HDMRRom
__interfaceDict['MSR'                 ] = MSR
__base                                  = 'superVisedLearning'

# def addToInterfaceDict(newDict):
#   for key,val in newDict.items():
#     __interfaceDict[key]=val

def returnInstance(ROMclass,caller,**kwargs):
  """
  This function return an instance of the request model type
  @In ROMclass: string representing the instance to create
  @In caller: object that will share its messageHandler instance
  @In kwargs: a dictionary specifying the keywords and values needed to create
              the instance.
  @ Out an instance of a ROM
  """
  try: return __interfaceDict[ROMclass](caller.messageHandler,**kwargs)
  except KeyError: caller.raiseAnError(NameError,'not known '+__base+' type '+str(ROMclass))

def returnClass(ROMclass,caller):
  """
  This function return an instance of the request model type
  @In ROMclass: string representing the class to retrieve
  @In caller: object that will share its messageHandler instance
  @ Out the class definition of a ROM
  """
  try: return __interfaceDict[ROMclass]
  except KeyError: caller.raiseAnError(NameError,'not known '+__base+' type '+ROMclass)
