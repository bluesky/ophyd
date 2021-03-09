#!/usr/bin/env python3

import argparse
import os
import re

import logging


def write_detector_class(tempfile, dev_name, det_name, cam_name):

    tempfile.write(
f'''
class {det_name}(DetectorBase):
    _html_docs = ['{dev_name}Doc.html']
    cam = C(cam.{cam_name}, 'cam1:')
''')


def parse_pv_structure(driver_dir):
    template_dir = driver_dir
    for dir in os.listdir(driver_dir):
        if dir.endswith('App'):
            template_dir = os.path.join(template_dir, dir, 'Db')
            break
    logging.debug(f'Found template dir: {template_dir}')
    
    template_files = []
    for file in os.listdir(template_dir):
        if file.endswith('.template'):
            template_files.append(os.path.join(template_dir, file))
            logging.debug(f'Found template file {file}')

    output = {}
    include_file = False
    for file in template_files:
        logging.debug(f'Collecting pv info from {os.path.basename(file)}')
        fp = open(file, 'r')
        
        lines = fp.readlines()
        for line in lines:
            if line.startswith('include "NDFile.template"'):
                logging.debug(f'Driver AD{dev_name} uses the NDFile.template file.')
                include_file = True

            if line.startswith('record'):
                pv_name = line.split(')')[2][:-1]
                if pv_name.endswith('_RBV'):
                    if pv_name[:-4] in output.keys():
                        logging.debug(f'Identified {pv_name[:-4]} as a record w/ RBV')
                        output[pv_name[:-4]] = 'SignalWithRBV'
                    else:
                        logging.debug(f'Identified read-only record {pv_name}')
                        output[pv_name] = 'EpicsSignalRO'
                else:
                    logging.debug(f'Found record {pv_name}')
                    output[pv_name] = 'EpicsSignal'

        fp.close()

    return output, include_file


def write_cam_class(tempfile, driver_template, include_file, dev_name, det_name, cam_name):
    file = ''
    if include_file:
        file = ', FileBase'
    tempfile.write(
f'''
class {cam_name}(CamBase{file}):
    _html_docs = ['{dev_name}Doc.html']
    _default_configuration_attrs = (
        CamBase._default_configuration_attrs
    )
''')

    for pv in driver_template.keys():
        pv_var_name = re.sub( '(?<!^)(?=[A-Z])', '_', pv ).lower()
        tempfile.write(f"    {pv_var_name} = ADCpt({driver_template[pv]}, '{pv}')\n")



def parse_args():

    parser = argparse.ArgumentParser(description='Utility for creating boilerplate ophyd classes')
    parser.add_argument('-t', '--target', help='Location of locally installed areaDetector driver folder structure.')
    parser.add_argument('-d', '--debug', action='store_true', help='Enable debug loogging for the script.')

    args = vars(parser.parse_args())

    log_level = logging.ERROR
    if args['debug']:
        log_level = logging.DEBUG

    if args['target'] is None:
        return os.path.abspath('.'), log_level
    else:
        return args['target'], log_level


if __name__ == '__main__':

    driver_dir, log_level = parse_args()
    if not os.path.exists(driver_dir) or not os.path.isdir(driver_dir):
        logging.error(f'Input {driver_dir} does not exist or is not a directory!')
        exit(-1)

    logging.basicConfig(level=log_level)

    driver_name = os.path.basename(driver_dir)
    if not driver_name.startswith('AD'):
        logging.error(f'Specified driver directory {driver_name} could not be identified as an areaDetector driver!')
        exit(-1)

    dev_name = driver_name[2:]
    det_name = f'{dev_name}Detector'
    cam_name = f'{det_name}Cam'
    logging.debug(f'Creating boilerplate for {dev_name}, with classes {det_name} and {cam_name}')

    tempfile = open(f'{det_name}_boilerplate.py', 'w')
    write_detector_class(tempfile, dev_name, det_name, cam_name)
    driver_template, include_file = parse_pv_structure(driver_dir)
    write_cam_class(tempfile, driver_template, include_file, dev_name, det_name, cam_name)
    tempfile.close()