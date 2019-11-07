#!/usr/bin/env python3
"""
Maquette log viewer utility

usage: log_viewer.py [-h] [-v] [-t] FILE

positional arguments:
  FILE                  Maquette LOG output

optional arguments:
  -h, --help            show this help message and exit
  -v, --verbose         set verbosity to INFO level (includes stats)
  -t, --tau             use CAMS AOT in stack bars plot

returns:
  Plot files as PNG
  Table ASCII csv file

Example:

    ./log_viewer.py -v toto.log

"""

__author__ = "J.Colin, CESBIO"
__license__ = "CC BY"
__version__ = "0.2.0"

import sys
import argparse
import numpy as np
import pylab as pl
import pandas as pd, re
from collections import OrderedDict
from pandas.plotting import register_matplotlib_converters

register_matplotlib_converters()


class Log:
    def __init__(self, log_file, tau_weight=False, verbose=False):

        # Catch args as attributes
        self._weight_by_tau = tau_weight
        self.verbose = verbose

        # DataFrame key labels
        self.lbl_date = 'Date'
        self.lbl_rh = 'RH'
        self.lbl_cloud = 'Cloud Fraction (with shadow)'
        self.lbl_cirrus = 'Cirrus Fraction'
        self.lbl_ozone = 'Ozone'
        self.lbl_avg_tau = 'Average tau'
        self.lbl_weight_prev_cams_date = 'Prev CAMS date weight'
        self.lbl_weight_next_cams_date = 'Next CAMS date weight'
        self.lbl_prev_aot = "Prev CAMS AOT"
        self.lbl_next_aot = "Next CAMS AOT"
        self.lbl_total_aot = "Total CAMS AOT"

        # Regex definitions for the MAQT log file
        self.regex_maqt_date = "^L1C"
        self.regex_maqt_rh = "^average"
        self.regex_maqt_cams_ratio = "^temporalInterpProps"
        self.regex_maqt_cloud_fraction = "couverture nuageuse \(avec ombres\)"
        self.regex_maqt_cirrus_fraction = "taux de cirrus"
        self.regex_maqt_ozone = "ozone"
        self.regex_maqt_prev_aot = "prev AOT"
        self.regex_maqt_next_aot = "next AOT"
        self.regex_maqt_weight_prev_cams_date = "weightPrevCAMSdate"
        self.regex_maqt_weight_next_cams_date = "weightNextCAMSdate"

        # Load log file content
        self._raw, self._log_file_name = self._get_file_text(log_file, verbose)

        # Parse MAQT log file
        # todo: test log file for MAQT or MAJA type
        self._date_list, self._rh_list, self._props_arr, self._props_list, self._cloud_list, self._cirrus_list, self._ozone_list, \
        self._weight_prev_cams_date_list, self._weight_next_cams_date_list, self._prev_aot_list, self._next_aot_list = self._parse_maqt_log()

        # Compute interpolated total AOT
        self._total_AOT_list = self._interpolate_total_aot()

        # Building an attribute df of type DataFrame
        self.df = self._building_maqt_dataframe()

        if verbose:
            pd.set_option('display.expand_frame_repr', False)
            print(self.df.describe())

    def _building_maqt_dataframe(self):
        try:
            df = pd.DataFrame(data={self.lbl_date: self._date_list,
                                    self.lbl_rh: self._rh_list,
                                    self.lbl_cloud: self._cloud_list,
                                    self.lbl_cirrus: self._cirrus_list,
                                    self.lbl_ozone: self._ozone_list,
                                    self.lbl_weight_prev_cams_date: self._weight_prev_cams_date_list,
                                    self.lbl_weight_next_cams_date: self._weight_next_cams_date_list,
                                    self.lbl_prev_aot: self._prev_aot_list,
                                    self.lbl_next_aot: self._next_aot_list,
                                    self.lbl_total_aot: self._total_AOT_list})

            props_df = pd.DataFrame(self._props_arr, columns=self._props_list)
            df = pd.concat([df, props_df], axis=1)
            return df

        except UnboundLocalError:
            print("ERROR: file %s doesn't seem to contain expected fields..." % self._log_file_name)
            print("       Is it really a log of MAQT?")
            sys.exit(1)

    @staticmethod
    def _extract_float_from_text(text, pos, sep=None, upto=False):
        if sep is not None:
            return float(text.split(sep)[pos])

        if upto:
            return float(text[pos:])

    @staticmethod
    def _get_file_text(filename, verbose=False):
        try:
            with open(filename, 'r') as f:
                raw = f.readlines()
                f.close()
                name = filename.split('/')[-1]

            if verbose:
                print("INFO: successfully opened %s" % filename)

            return raw, name

        except FileNotFoundError:
            print("ERROR: file %s not found..." % filename)
            sys.exit(1)

    def _interpolate_total_aot(self):
        return np.array(self._weight_prev_cams_date_list) \
               * np.array(self._prev_aot_list) \
               + np.array(self._weight_next_cams_date_list) \
               * np.array(self._next_aot_list)

    def _parse_maqt_log(self):
        date_list = []  # List of L1C products used
        rh_list = []  # List of average relative humidity
        props_list = []  # List of aerosol models proportion
        cloud_list = []  # List of cloud fraction with shadow
        cirrus_list = []  # List of cirrus fraction
        ozone_list = []  # List of ozone TODO: define unit
        weight_prev_cams_date_list = []
        weight_next_cams_date_list = []
        prev_aot_list = []
        next_aot_list = []

        for line in range(len(self._raw)):
            # Extract list of date
            if re.search(self.regex_maqt_date, self._raw[line]) is not None:
                date_list.append(pd.to_datetime(self._raw[line][10:18], format='%Y%m%d'))

            # Extract relative humidity
            if re.search(self.regex_maqt_rh, self._raw[line]) is not None:
                rh_list.append(float(self._raw[line].split(':')[1]))

            # Extract models proportion
            if re.search(self.regex_maqt_cams_ratio, self._raw[line]) is not None:
                temporal_interp_props = OrderedDict(sorted(eval(self._raw[line].split(':')[1])))
                if not props_list:
                    props_arr = np.array(list(temporal_interp_props.values()))
                    props_list = temporal_interp_props.keys()
                else:
                    # props_arr seems referenced before assignment here, but any error will be caught
                    # by the 'UnboundLocalError' exception handler later on. Anyway, the former if
                    # clause should 'always' initialize it
                    props_arr = np.vstack((props_arr, list(temporal_interp_props.values())))

            # Extract cloud fraction
            if re.search(self.regex_maqt_cloud_fraction, self._raw[line]) is not None:
                cloud_list.append(float(self._raw[line].split(':')[2].strip('%\n')) / 100)

            # Extract cirrus fraction
            if re.search(self.regex_maqt_cirrus_fraction, self._raw[line]) is not None:
                cirrus_list.append(self._extract_float_from_text(self._raw[line], 14, upto=True))

            # Extract ozone
            if re.search(self.regex_maqt_ozone, self._raw[line]) is not None:
                ozone_list.append(self._extract_float_from_text(self._raw[line], 1, '='))

            # Extract previous CAMS weights
            if re.search(self.regex_maqt_weight_prev_cams_date, self._raw[line]) is not None:
                weight_prev_cams_date_list.append(self._extract_float_from_text(self._raw[line], 1, ':'))

            # Extract previous CAMS weights
            if re.search(self.regex_maqt_weight_next_cams_date, self._raw[line]) is not None:
                weight_next_cams_date_list.append(self._extract_float_from_text(self._raw[line], 1, ':'))

            # Extract previous CAMS AOT
            if re.search(self.regex_maqt_prev_aot, self._raw[line]) is not None:
                prev_aot_dict = OrderedDict(sorted(eval(self._raw[line].split(':')[1])))
                prev_aot_list.append(np.array(list(prev_aot_dict.values())).sum())

            # Extract next CAMS AOT
            if re.search(self.regex_maqt_next_aot, self._raw[line]) is not None:
                next_aot_dict = OrderedDict(sorted(eval(self._raw[line].split(':')[1])))
                next_aot_list.append(np.array(list(next_aot_dict.values())).sum())

        return date_list, rh_list, props_arr, props_list, cloud_list, cirrus_list, ozone_list, \
               weight_prev_cams_date_list, weight_next_cams_date_list, prev_aot_list, next_aot_list

    def _set_aerosols_list(self):
        return self._props_list

    def plot_clouds(self):
        fig, ax1 = pl.subplots(figsize=(12, 6))

        ax1.bar(self.df[self.lbl_date], self.df[self.lbl_cloud], label=self.lbl_cloud)
        ax1.set_ylabel('Fraction (-)')
        pl.legend()

        fig.autofmt_xdate()
        pl.title(self._log_file_name)
        pl.savefig(self._log_file_name[:-4] + "_clouds.png")

    def plot_aerosols(self):
        fig, ax1 = pl.subplots(figsize=(12, 6))

        aerosols = self._set_aerosols_list()

        stack = 0
        for aerosol in aerosols:
            if self._weight_by_tau:
                ax1.bar(self.df[self.lbl_date], self.df[aerosol] * self.df[self.lbl_total_aot], bottom=stack,
                        label=aerosol)
                stack += self.df[aerosol] * self.df[self.lbl_total_aot]
            else:
                ax1.bar(self.df[self.lbl_date], self.df[aerosol], bottom=stack, label=aerosol)
                stack += self.df[aerosol]

        ax1.xaxis.set_major_formatter(pl.DateFormatter("%y/%m/%d"))
        ax1.xaxis.set_minor_formatter(pl.DateFormatter("%d"))
        ax1.set_ylabel('CAMS AOT with aerosol fractions (-)')
        pl.legend()

        ax2 = ax1.twinx()
        ax2.set_ylabel('Relative humidity (%)')
        ax2.plot(self.df[self.lbl_date], self.df[self.lbl_rh])

        fig.autofmt_xdate()
        pl.title(self._log_file_name)
        pl.savefig(self._log_file_name[:-4] + "_aerosols.png")

    def save_table(self):
        with open(self._log_file_name[:-4] + "_table.csv", 'w') as f:
            f.write(self.df.to_string())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("FILE", help="MiniLut File")
    parser.add_argument("-v", "--verbose", help="Set verbosity to INFO level + interactive plotting",
                        action="store_true")
    parser.add_argument("-t", "--tau", help="Weight aerosols with tau", action="store_true")

    args = parser.parse_args()

    log = Log(args.FILE, args.tau, args.verbose)
    log.plot_aerosols()
    log.plot_clouds()
    log.save_table()

    print("INFO: Done...")
    sys.exit(0)


if __name__ == "__main__":
    main()
