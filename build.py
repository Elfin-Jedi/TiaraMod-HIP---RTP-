helpString = """
A lightweight (regex, no parsing) script that allows you to store the english localisation right were you need it. \n
How to use:
	<<KEY;"Your localisation text.">>
Example:
	character_event = {
		id = N.1
		desc = <<EVTDESC.N.1_A;"First possible text">>
		desc = <<EVTDESC.N.1_B;
			"You can also split the text 
			over multiple lines for easier readiblity.\n
			Keep in mind that newlines and tabs will be removed, so use \n,\t as usual.">>
		...
	}
This script will transform this into two files: One for the event and one for localisation.
	character_event = {
		id = N.1
		desc = EVTDESC.N.1_A
		desc = EVTDESC.N.1_B
		...
	}
And:
	EVTDESC.N.1_A;First possible text;;;;;;;;;;;;;x
	EVTDESC.N.1_B;You can also split the text over multiple lines for easier readiblity.\nKeep in mind that newlines and tabs will be removed, so use \n,\t as usual.;;;;;;;;;;;;;
	...
	
In case you translate your localisation, you might want to change the output path for the localisation files (so that nothing is overwritten). To do so, change the locDir function.
The TRUNCATE_LIMIT limits the amount of characters of the directory name that are used for the localisation filename. The reason that the dir name is part of the
filename is to prevent different files with the same name from different folders overwriting themselves.
"""
import re
import os
import argparse

import sys
from io import StringIO
import contextlib
TRUNCATE_LIMIT = 30
SCRIPT_FILE_TYPE = ".ck2script"
MACRO_FILE_TYPE = ".ck2macro"
MACRO_RECURSION_LIMIT = 42
MACRO_CODE_EXECUTION = True #allows python code execution. Don't execute unknown code!
def locDir(rootDir):
	return rootDir + "\\localisation\\"

LOC_ENTRIES = []
GLOBAL_MACROS = []



@contextlib.contextmanager
def stdoutIO(stdout=None):
    old = sys.stdout
    if stdout is None:
        stdout = StringIO()
    sys.stdout = stdout
    yield stdout
    sys.stdout = old


def readMacros(text):
	pattern = re.compile(r'[@]beginmacro[ \t\n]+([A-Za-z0-9_]+)[(]([^)]*?)[)]:[\n\r\t ]*((.|[\n\r\t ])*?)[@]endmacro')
	#group 0: macroname, group 1: arguments, group 2: replacement
	macro_matches = pattern.findall(text)
	return macro_matches
def macroEffectWithArguments(macro, argumentValues):
	argumentNames = macro[1].split(',')
	if len(argumentNames) != len(argumentValues):
		print("Error, arguments not matching: \n")
		print(argumentNames)
		print(argumentValues)
		exit()
	effect = macro[2]
	for i in range(0,len(argumentNames)):
		effect = effect.replace(argumentNames[i].strip(), argumentValues[i].strip())
	effect = effect.rstrip() #remove trailing whitespace/tabs/newlines
	return effect
def splitArguments(argstring):
	tokens = [t for t in re.split(r",?\"(.*?)\",?|,", argstring) if t is not None and len(t.strip())>0]
	tokens = [t for t in re.split(r",(?=(?:[^\"]*\"[^\"]*\")*[^\"]*$)", argstring) if t is not None and len(t.strip())>0]
	if len(tokens) == 0:
		return [argstring]
	return tokens
def applyMacro(text,macro):
	pattern = re.compile(r'[@]('+re.escape(macro[0]) +')[(]([^)]*?)[)]')
	#group 1: macroname, group 2: arguments
	new_text = pattern.sub(lambda match: macroEffectWithArguments(macro, splitArguments(match[2])), text)
	return new_text
def applyPythonEvalMacro(text):
	pattern = re.compile(r'[@](python)[(]((?:[\s\S](?![)]##))*)[)]endpython')
	pattern = re.compile(r'[@](python)[(]((?:[\s\S](?!endpython))*)[)]endpython')
	#group 1: macroname, group 2: arguments
	def evaluateMacroMatch(match):
		arguments = splitArguments(match[2])
		parameterNames = [s.strip() for s in arguments[0][1:-1].split(",")]
		code = arguments[1].strip()[1:-1]
		parameterValues = arguments[2:]
		if len(parameterNames) != len(parameterValues):
			print("Parameter mismatch:", parameterNames, parameterValues)
			exit()
		globals_dict = dict(zip(parameterNames, parameterValues))
		with stdoutIO() as s:
			exec(code,globals_dict)
		output = s.getvalue()
		return output
	new_text = pattern.sub(lambda match: evaluateMacroMatch(match), text)
	return new_text
def applyMacros(text, macros):
	for macro in macros:
		text = applyMacro(text, macro)
	return text
def clearMacros(text):
	pattern = re.compile(r'[@]beginmacro[ \t\n]+([A-Za-z0-9_]+)[(]([^)]*?)[)]:[\n\r\t ]*((.|[\n\r\t ])*?)[@]endmacro')
	#group 0: macroname, group 1: arguments, group 2: replacement
	new_text = pattern.sub("", text)
	return new_text
def containsMacros(text):
	pattern = re.compile(r'[@]([A-Za-z0-9_]+)[(]([^)]*?)[)]')
	return pattern.search(text)

def writeLocToFile(filename):
	global LOC_ENTRIES
	if len(LOC_ENTRIES) == 0:
		return
	filecontent = ""
	for entry in LOC_ENTRIES:
		filecontent = filecontent + entry
	locFile = open(filename, "w")
	locFile.write(filecontent)
	locFile.close()
	LOC_ENTRIES = []
def addLocalisation(key, englishText):
	global LOC_ENTRIES
	englishText = englishText.replace('\t','').replace('\n','').replace('\r','')
	locEntry = key + ";" + englishText + ";;;;;;;;;;;;;x\n"  
	LOC_ENTRIES.append(locEntry)
"""Find all localisation entries and store them. Return new content with proper loc keys"""
def processFileContent(text):
	pattern = re.compile(r'<<([A-Za-z_\-.0-9]*)[\n\r\t ]*[;][\n\r\t ]*["]([\s\S]*?)["]>>')
	matches = pattern.findall(text) #list of (key, loctext)
	for match in matches:
		addLocalisation(match[0], match[1])
	new_content = pattern.sub(r"\1", text)
	return new_content
	"""Fetch all localisation entries. Write new .txt file and loc file."""
def processMacroFile(dirName, filename):
	global rootDir
	global GLOBAL_MACROS
	filepath = dirName + "\\" + filename
	scriptFile = open(filepath, "r")
	content = scriptFile.read()
	GLOBAL_MACROS = GLOBAL_MACROS + readMacros(content)
	scriptFile.close()
def processFile(dirName,filename):
	global rootDir
	global GLOBAL_MACROS
	global MACRO_RECURSION_LIMIT
	filepath = dirName + "\\" + filename
	scriptFile = open(filepath, "r")
	content = scriptFile.read()
	#apply macros
	LOCAL_MACROS = readMacros(content)
    
	new_content = clearMacros(content)
	counter = 0
	while containsMacros(new_content):
		if MACRO_CODE_EXECUTION:
			new_content = applyPythonEvalMacro(new_content)
		new_content = applyMacros(new_content, GLOBAL_MACROS)
		new_content = applyMacros(new_content, LOCAL_MACROS)
		if counter > MACRO_RECURSION_LIMIT:
			print("Macro recursion too deep.")
			exit()
		counter += 1
	new_content = processFileContent(new_content) # localisation only
	scriptFile.close()
	
	scriptTxtFilename = filename.replace(SCRIPT_FILE_TYPE, ".txt")
	scriptTxtFilePath = dirName + "\\" + scriptTxtFilename
	scriptTxtFile = open(scriptTxtFilePath, "w")
	scriptTxtFile.write(new_content)
	scriptTxtFile.close()
	
	locFilename = filename.replace(SCRIPT_FILE_TYPE, ".csv")
	#organize filenames so that they contain their directory. This allows you to have .ck2script files with the same name in different directories...
	locdirname = dirName.replace("\\","_").replace(".","")
	parts = locdirname.split("_")
	delim = "_"
	if len(parts) > 1:
		parts[1] = parts[1][:2] 
	locdirname = delim.join(parts)[:TRUNCATE_LIMIT]
	locFilepath = locDir(rootDir) + "LOC_"+locdirname+"_" +locFilename
	writeLocToFile(locFilepath)

def processDir(rootDir):
	if not os.path.exists(locDir(rootDir)):
		os.makedirs(locDir(rootDir))
	for dirName, subdirList, fileList in os.walk(rootDir):
		contains_script = any(map(lambda fname: fname.endswith(SCRIPT_FILE_TYPE), fileList)) or ((dirName == rootDir) and any(map(lambda fname: fname.endswith(MACRO_FILE_TYPE), fileList)) )
		if not contains_script:
			continue
		print('Directory: %s' % dirName)
		for fname in fileList:
			if fname.endswith(SCRIPT_FILE_TYPE):
				print('\t%s' % fname)
				processFile(dirName, fname)
			if fname.endswith(MACRO_FILE_TYPE) and dirName == rootDir:
				print('\t%s' % fname)
				processMacroFile(dirName, fname)
				
if __name__ == '__main__':
	rootDir = '.'
	parser = argparse.ArgumentParser(description = helpString)
	parser.add_argument("--dir", "-d", help="set main mod directory, default is the working directory")
	parser.add_argument("--filetype", "-f", help="set filetype of the processed scripts, default .ck2script")
	args = parser.parse_args()
	if args.dir:
		rootDir = args.dir
		print("Root dir is" % rootDir)
	if args.filetype:
		SCRIPT_FILE_TYPE = args.filetype
		print("Filetype is " % args.filetype)
	processDir(rootDir)

	


'''
add macro file for global macros,

@beginmacro medium_cost():
	12
@endmacro
@beginmacro mymacro(param1, param2,...):
	add_opinion{who = param1 value = param2}
@endmacro

somewhere later

effect = {
	@mymacro(event_target:priest, 12)
	wealth = -@medium_cost()
}
'''