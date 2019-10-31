#!/usr/bin/env python3
"""
Maquette log viewer utility

usage: log_viewer.py [-h] [-v]  FILE

positional arguments:
  FILE                  Maquette LOG output

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         Set verbosity to INFO level + prints stats

returns:
  Plot files as PNG

Example:

    ./log_viewer.py -v toto.log

"""

__author__ = "J.Colin, CESBIO"
__license__ = "CC BY"
__version__ = "0.1.0"

import sys
import argparse
import numpy as np
import pylab as pl
import pandas as pd, re
from collections import OrderedDict
from pandas.plotting import register_matplotlib_converters

register_matplotlib_converters()


class Log():
    def __init__(self, log_file, verbose=False):
        try:
            with open(log_file, 'r') as f:
                self.raw = f.readlines()
                f.close()
                self.name = log_file.split('/')[-1]

            if verbose:
                print("INFO: successfuly opened %s" % log_file)

        except FileNotFoundError:
            print("ERROR: file %s not found..." % log_file)
            sys.exit(1)

        date_list   = []  # List of L1C products used
        rh_list     = []  # List of average relative humidity
        props_list  = []  # List of aerosol models proportion
        cloud_list  = []  # List of cloud fraction with shadow
        cirrus_list = []  # List of cirrus fraction

        for line in range(len(self.raw)):
            # Extract list of date
            if re.search("^L1C", self.raw[line]) is not None:
                date_list.append(pd.to_datetime(self.raw[line][10:27], format='%Y%m%d%Z%H%M%S'))

            # Extract relative humidity
            if re.search("^average", self.raw[line]) is not None:
                rh_list.append(float(self.raw[line].split(':')[1]))

            # Extract models proportion
            if re.search("^temporalInterpProps", self.raw[line]) is not None:
                temporal_interp_props = OrderedDict(sorted(eval(self.raw[line].split(':')[1])))
                if not props_list:
                    props_arr = np.array(list(temporal_interp_props.values()))
                    props_list = temporal_interp_props.keys()
                else:
                    props_arr = np.vstack((props_arr, list(temporal_interp_props.values())))

            # Extract cloud fraction
            if re.search("couverture nuageuse \(avec ombres\)", self.raw[line]) is not None:
                cloud_list.append(float(self.raw[line].split(':')[2].strip('%\n'))/100)

            # Extract cirrus fraction
            if re.search("taux de cirrus", self.raw[line]) is not None:
                cirrus_list.append(float(self.raw[line][14:]))

        # Building a DataFrame attribute
        self.df = pd.DataFrame(data={'Date': date_list,
                                     'RH': rh_list,
                                     'Cloud Fraction w Shadow': cloud_list,
                                     'Cirrus Fraction': cirrus_list})

        props_df = pd.DataFrame(props_arr, columns=props_list)
        self.df = pd.concat([self.df, props_df], axis=1)
        self.aerosols = props_list

        if verbose:
            pd.set_option('display.expand_frame_repr', False)
            print(self.df.describe())

    def plot_props(self):
        fig, ax1 = pl.subplots(figsize=(12, 6))

        stack = 0
        for aerosol in self.aerosols:
            ax1.bar(self.df['Date'], self.df[aerosol], bottom=stack, label=aerosol)
            stack += self.df[aerosol]

        ax1.xaxis.set_major_formatter(pl.DateFormatter("%y/%m/%d"))
        ax1.xaxis.set_minor_formatter(pl.DateFormatter("%d"))
        ax1.set_ylabel('Aerosols fraction (-)')
        pl.legend()

        ax2 = ax1.twinx()
        ax2.set_ylabel('Relative humidity (%)')
        ax2.plot(self.df['Date'], self.df['RH'])

        fig.autofmt_xdate()
        pl.title(self.name)
        pl.savefig(self.name[:-4] + "_aerosols.png")

    def plot_clouds(self):
        fig, ax1 = pl.subplots(figsize=(12, 6))

        ax1.bar(self.df['Date'], self.df['Cloud Fraction w Shadow'], label='Cloud Fraction Shd')
        ax1.set_ylabel('Fraction (-)')
        pl.legend()

        fig.autofmt_xdate()
        pl.title(self.name)
        pl.savefig(self.name[:-4] + "_clouds.png")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("FILE", help="MiniLut File")
    parser.add_argument("-v", "--verbose", \
                        help="Set verbosity to INFO level + interactive plotting", \
                        action="store_true")

    args = parser.parse_args()

    log = Log(args.FILE, args.verbose)
    log.plot_props()
    log.plot_clouds()

    print("INFO: Done...")
    sys.exit(0)


if __name__ == "__main__":
    main()
