#!/usr/bin/env python3

import json
from pathlib import Path
import logging
import inspect       # to get the name of function within a function
import errno
from string import Template
import zipfile as zf
import argparse
from posix import abort
from pathvalidate import sanitize_filename, sanitize_filepath

logger_main = logging.getLogger(__name__)
if __name__ == "__main__":
    LOGGER_LEVEL_MAIN = logging.DEBUG
else:
    LOGGER_LEVEL_MAIN = logging.INFO
    
logger_main.setLevel(level=LOGGER_LEVEL_MAIN)
LOGGER_FUNC_LEVEL = logging.INFO    # DEBUG, INFO, WARNING, ERROR, CRITICAL

def title_extract(content):
    '''Extract title from the "content" of the json file
    
    Input example (a string):
        "# C & Cpp Language\r\n\r\n(keywords: c, c++) ...(more)..."
    Return example (a string):
        "C & Cpp Language"
    '''
    first_line = content.splitlines()[0]
    # Note: the first line might or might not start with a "#" 
    if len(first_line.split("#")[0]) == 0:
        title = first_line.split("#")[1].strip()
    else:
        title = first_line.split("#")[0].strip()
    return title

def date_convert(date_in):
    '''input format: "2022-08-24T18:32:58.089Z", 
       convert to
       output format = "2022-09-03 03:49:30Z"
    '''
    ds = date_in.split("T")
    ds1 = ds[1].split(".")
    date_out = ds[0] + " " + ds1[0] + "Z"
    return date_out

def front_matter(d_in):
    '''Constract the "front matter" of the Joplin note
    
    Input example (a dictionary):
      {
      "id": "0bb18b5d-a6d1-4fc3-9e2b-1829b31b60ad",
      "content": "# C & Cpp Language\r\n\r\n(keywords: c, c++) ...(more)...",
      "creationDate": "2022-08-24T18:32:58.089Z",
      "lastModified": "2022-09-03T15:33:44.948Z",
      "markdown": true
      }
    Return example (two strings):
        "title" , 
        "---
        title: 'C & Cpp Language'
        updated: 2022-08-24 18:32:58Z
        created: 2022-09-03 15:33:44Z
        latitude: 0.00000000
        longitude: 0.00000000
        altitude: 0.0000
        ---"
    '''
    name_func = inspect.stack()[0][3]
    name_caller = inspect.stack()[1][3]
    logger = logging.getLogger(name_func)
    if name_caller == "<module>":
        logger.setLevel(level=logging.DEBUG)
    else:
        logger.setLevel(level=LOGGER_LEVEL_MAIN)
        
    OUT_TEMPLATE = "---\r\n" + \
        "title: \'$title\'\r\n" + \
        "updated: $date_modify\r\n" + \
        "created: $date_create\r\n" + \
        "latitude: 0.00000000\r\n" + \
        "longitude: 0.00000000\r\n" + \
        "altitude: 0.0000\r\n" + \
        "---\r\n" + "\r\n"   
    
    contain = d_in["content"]
    title = title_extract(contain)
    title = sanitize_filename(title)    # replaced invalid character(s) 
    title = title.replace("'", "''")    # in case such as "Wheeler's Delay"
    logger.debug(f"title = {title}")
    
    date_create = date_convert(d_in["creationDate"])
    date_modify = date_convert(d_in["lastModified"])
    logger.debug(f"date_create = {date_create} ; date_modify = {date_modify}")
    
    fout_front = Template(OUT_TEMPLATE).substitute(title=title, 
                                                   date_modify=date_modify,
                                                   date_create=date_create)
    logger.debug(f"{fout_front}")
    return title, fout_front
    
def file_write(fout_name, data_out, overwrite=False, dry=False):
    '''Open a file "fw" for writing and handle all errors
    
    input:
        fout_name = full file name with path (string)
        data_out = data to be wrtten to "fw" (string)
        overwrite = overwrite file if exist already
    
    return: False = if file written succefully, otherwise
            True = operation failed
    '''
    name_func = inspect.stack()[0][3]
    name_caller = inspect.stack()[1][3]
    logger = logging.getLogger(name_func)
    if name_caller == "<module>":
        logger.setLevel(level=logging.DEBUG)
        # logger.setLevel(level=LOGGER_LEVEL_MAIN)
    else:
        logger.setLevel(level=LOGGER_LEVEL_MAIN)

    flag_abort = True
    if overwrite == False:
        mode = "x"        # x will fail if the file already exists.
    else:
        mode = "w"
    try:
        if dry is True:
            # print(f'{fout_name.name}')
            flag_abort = False
        else:
            with open(fout_name, mode) as f:     
                f.write(data_out)
                flag_abort = False
    except IOError as e:
        if fout_name.exists():
            ans = input(f'File "{fout_name.name}" already exist. Overwrite? y/(n)')
            if ans.upper() == "Y" or ans.upper() == "YES":
                logger.info(f'File "{fout_name.name}" will be overwritten.')
                logger.debug(f"(ok to overwrite) ans = {ans}; flag_abort = {flag_abort}")
                flag_abort = file_write(fout_name, data_out, True)
            else:
                logger.debug(f"(should not overwrite) ans = {ans}; flag_abort = {flag_abort}")
                pass
        elif e.errno == errno.ENOENT:     # No such file or directory (must be dir here)
            fout_path = fout_name.parent
            logger.debug(f"fout_path = {fout_path}")
            logger.debug(f"fout_path.exists() = {fout_path.exists()}")   # should not exist (or false)
            flag_mkdir = False
            try:
                fout_path.mkdir()
                flag_abort = file_write(fout_name, data_out, True)
            except Exception as e:
                logger.error(f"Error - can't create directory {fout_path}: {e}")
        else:
            logger.error(f"(I/O)Error - {e}, e.errno = {e.errno}")
    except Exception as e:
        logger.error(f"Error - encounter unexpected error: {e}")

    logger.debug(f"(before return) flag_abort = {flag_abort}")
    return flag_abort

def joplin_file_create(d_in, path=None, verb=True, dry=False):
    '''Create a markdown file for importing of Joplin note
    
    Input example (a dictionary):
      {
      "id": "0bb18b5d-a6d1-4fc3-9e2b-1829b31b60ad",
      "content": "# C & Cpp Language\r\n\r\n(keywords: c, c++) ...(more)...",
      "creationDate": "2022-08-24T18:32:58.089Z",
      "lastModified": "2022-09-03T15:33:44.948Z",
      "markdown": true
      }
      
    "path" is the directory for the output file.
    If "path" is None, then the output file will be created in the current working one.
    Otherwise, the path of file created is specified by the input "path". 
    
    "verb" => True (default) to turn on the verbose mode
                file name of conversion will be sent to stdout
           => False, silent mode, 
           
    "dry" => True, just print out file name but no file will be generated.
            when dry=True, the "verb" will be forced to True also
          => False (default), 
      
    (Output) contains of created file example:
        ---
        title: 'C & Cpp Language'
        updated: 2022-08-24 18:32:58Z
        created: 2022-09-03 15:33:44Z
        latitude: 0.00000000
        longitude: 0.00000000
        altitude: 0.0000
        ---
        # C & Cpp Language

        (keywords: c, c++)

        Resources:
        1. Learn C++ :  a free website devoted to teaching you how to program in C++. [here][resrc-1]   
        2. Books, a list of C++ books on [Free Book Centre]   
        3. Coding for Everyone: C and C++ Specialization, on [Coursera][resrc-3]   
        ......
        (...... more ......)
        ......
        
    return: False = file written succefully
            True = operation failed
    '''
    flag_abort = True
    if dry:
        verb = True
    name_func = inspect.stack()[0][3]
    name_caller = inspect.stack()[1][3]
    logger = logging.getLogger(name_func)
    if name_caller == "<module>":
        logger.setLevel(level=logging.DEBUG)
    else:
        logger.setLevel(level=LOGGER_LEVEL_MAIN)

    if path is None:
        f_path = pathlib.Path.cwd()
    else:
        f_path = path
        logger.debug(f"cwd = {Path.cwd()}")
        
    title, fout_front = front_matter(d_in)
    fout_name = Path(f_path).joinpath(title).with_suffix('.md')
    logger.debug(f"fout = {fout_name}")
    
    if verb:
        print(f'{fout_name.name}')
    is_md = d_in["markdown"]
    if is_md is not True:
        log_msg = f'Format of "{fout_name.name}" is not supported. Result is not known'
        logger.warning(log_msg)
        
    data_out = fout_front + d_in["content"]
    flag_abort = file_write(fout_name, data_out, overwrite=False, dry=dry)
       
    return flag_abort

def zip_json_rd(fzip_json):
    '''Read notes.json in the zip file
    
    Input: notes.zip (exported from Simplenote)
    
    Return: data of note (a dictionary)
    (example)
        {
          "activeNotes": [
            {
              "id": "0bb18b5d-a6d1-4fc3-9e2b-1829b31b60ad",
              "content": "# C & Cpp Language\r\n\r\n(keywords: c, c++) ...(more)...",
              "creationDate": "2022-08-24T18:32:58.089Z",
              "lastModified": "2022-09-03T15:33:44.948Z",
              "markdown": true
            },
            {
              "id": "8077b1d6-3fc1-40b9-9348-07841ec7bb02",
              "content": "# To Do List \r\n\r\n## my Simplenote testing ...(more)...",
              "creationDate": "2022-06-27T14:25:14.903Z",
              "lastModified": "2022-09-03T17:20:26.931Z",
              "markdown": true
            },
           ......
           (......more......)
           ......
    '''
    PATH_FJOSN = "source/notes.json"    # path of notes.json in ZIP file

    name_func = inspect.stack()[0][3]
    name_caller = inspect.stack()[1][3]
    logger = logging.getLogger(name_func)
    if name_caller == "<module>":
        logger.setLevel(level=logging.DEBUG)
    else:
        logger.setLevel(level=LOGGER_LEVEL_MAIN)

    data = None
    try:
        with zf.ZipFile(fzip_json, "r") as note_archive:
            file_json = PATH_FJOSN       # "source/notes.json"
            try:
                with note_archive.open(file_json, "r") as notes_json:
                    data = json.load(notes_json)
            except Exception as e:
                logger.error(f"Error - {e}")
    except zf.BadZipFile as e:
        logger.error(f"Bad Zip File - {e}")
    except Exception as e:
        logger.error(f"Error - {e}")
    return data

def arg_input():
    '''Get arguments of input file, output file, and others 
    '''
    msg_descript = 'Convert Simplenote to Joplin note.'
    parser = argparse.ArgumentParser(description=msg_descript)
    msg_f_in = 'input file => zip file exported from Simplenote.'
    parser.add_argument('f_in', type=str, help=msg_f_in)
    msg_f_out = 'output directory for files after conversion'
    parser.add_argument('f_out', type=str, help=msg_f_out)
    msg_verb = 'turn on the verbose mode'
    parser.add_argument('-v', '--verb', action='store_false', help=msg_verb)
    msg_dry = 'Dry run ......'
    parser.add_argument('-d', '--dry', action='store_true', help=msg_dry)
    args = parser.parse_args()

    return args.f_in, args.f_out, args.verb, args.dry

def main():
    f_in, f_out, verb, dry = arg_input()
    f_in_name = Path(f_in).name
    msg_pnt = f'Convert "{f_in_name}" to markdown+front_matter ' + \
                f'and saved under {f_out}' 
    print(msg_pnt)
    # exit()

    data = zip_json_rd(f_in)
    if data is None:
        print(f"rror encountered - {f_in_name.name} can't extract data")
        exit()
        
    if dry:
        print(f'Start file conversion ...... (Dry run) ......')
    else:
        print(f'Start file conversion......')
    for i, d_record in enumerate(data['activeNotes']):
        if i > 3 and RUN_LIMITED:     # to limit the number of running
            break
        try:
            flag_abort = joplin_file_create(d_record, f_out, verb, dry)
            if flag_abort:
                ans = input(f'Error encountered. Continue? y/(n)')
                if ans.upper() == "Y" or ans.upper() == "YES":
                    continue
                else:
                    print(f'Prgram aborted!!!')
                    break
        except Exception as e:
            logger_main.error(f'Unexpect Error encountered: {e}')
    print(f'End file conversion......')

if __name__ == "__main__":
    RUN_LIMITED = False         # True for debugging - to limit the data size
    main()



