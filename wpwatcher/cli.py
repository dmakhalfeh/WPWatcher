"""
Wordpress Watcher
Automating WPscan to scan and report vulnerable Wordpress sites

DISCLAIMER - USE AT YOUR OWN RISK.
"""

# Main program, parse the args, read config and launch scans
import time
import argparse
import shlex
import json
import sys

from wpwatcher import VERSION, AUTHORS, GIT_URL, log, init_log
from wpwatcher.utils import parse_timedelta, results_summary
from wpwatcher.config import WPWatcherConfig
from wpwatcher.core import WPWatcher
from wpwatcher.db import WPWatcherDataBase
from .daemon import WPWatcherDaemon

class WPWatcherCLI():
    def __init__(self):
        args=self.parse_args()
        init_log(args.verbose, args.quiet)
        # If template conf , print and exit
        if args.template_conf: self.template_conf()
        log.info("WPWatcher -  Automating WPscan to scan and report vulnerable Wordpress sites")
        # If version, print and exit
        if args.version: self.verion()
        # Init WPWatcher obhect and dump reports
        if args.wprs!=False: self.wprs(args.wprs, args.daemon)
        # Read config
        configuration=self.build_config_cli(args)
        
        # If daemon lopping
        if configuration['daemon']: 
            # Run 4 ever
            WPWatcherDaemon(configuration)
           
        else:
            # Run scans and quit
            # Create main object
            wpwatcher=WPWatcher(configuration)
            exit_code,results=wpwatcher.run_scans_and_notify()
            exit(exit_code)
            
    @staticmethod
    def wprs(filepath=None, daemon=False):
        db=WPWatcherDataBase(filepath, daemon=daemon)
        print(results_summary(db._data))
        exit(0)
    @staticmethod
    def verion():
        log.info("Version:\t\t%s"%VERSION)
        log.info("Authors:\t\t%s"""%AUTHORS)
        exit(0)
    @staticmethod
    def template_conf():
        print(WPWatcherConfig.TEMPLATE_FILE)
        exit(0)

    # Arguments can overwrite config file values
    @staticmethod
    def parse_args():
        parser = argparse.ArgumentParser(description="""WordPress Watcher is a Python wrapper for WPScan that manages scans on multiple sites and reports by email.
    Some config arguments can be passed to the command.
    It will overwrite previous values from config file(s).
    Check %s for more informations."""%(GIT_URL), formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument('--conf', '-c', metavar='File path', help="""The script * must read a configuration file to set mail server settings, WPScan path and other options *.     
    If no config file is found, mail server settings will have default values.  
    Setup mail server settings and turn on `send_email_report` in the config file if you want to receive reports.  
    You can specify multiple files `--conf File path [File path ...]`. Will overwrites the keys with each successive file.
    If not specified with `--conf` parameter, will try to load config from file `~/.wpwatcher/wpwatcher.conf`, `~/wpwatcher.conf` and `./wpwatcher.conf`.
    All options can be missing from config file.\n\n""", nargs='+', default=None)
        parser.add_argument('--template_conf', '--tmpconf', help="""Print a template config file.
    Use `wpwatcher --template_conf > ~/.wpwatcher/wpwatcher.conf && vim ~/.wpwatcher/wpwatcher.conf` to create (or overwrite) and edit the new default config file.""", action='store_true')
        parser.add_argument('--version', '-V', help="Print WPWatcher version", action='store_true')
        parser.add_argument('--wprs', metavar="Path to json file", help="Print database (wp_reports in config) summary. Leave path blank to find default file. Can be used with --daemon to print default daemon databse.", nargs='?', default=False)

        # Declare arguments that will overwrite config options
        parser.add_argument('--wp_sites', '--url', metavar="URL", help="Configure wp_sites", nargs='+', default=None)
        parser.add_argument('--wp_sites_list', '--urls', metavar="File path", help="Configure wp_sites from a list of URLs", default=None)
        parser.add_argument('--email_to', '--em', metavar="Email", help="Configure email_to", nargs='+', default=None)
        parser.add_argument('--send_email_report', '--send', help="Configure send_email_report=Yes", action='store_true')
        parser.add_argument('--send_infos', '--infos', help="Configure send_infos=Yes", action='store_true')
        parser.add_argument('--send_errors', '--errors', help="Configure send_errors=Yes", action='store_true')
        parser.add_argument('--attach_wpscan_output', '--attach', help="Configure attach_wpscan_output=Yes", action='store_true')
        parser.add_argument('--fail_fast', '--ff', help="Configure fail_fast=Yes", action='store_true')
        parser.add_argument('--api_limit_wait', '--wait', help="Configure api_limit_wait=Yes", action='store_true')
        parser.add_argument('--daemon',  help="Configure daemon=Yes", action='store_true')
        parser.add_argument('--daemon_loop_sleep','--loop', metavar='Time string', help="Configure daemon_loop_sleeps")
        parser.add_argument('--wp_reports', '--reports', metavar="File path", help="Configure wp_reports", default=None)
        parser.add_argument('--resend_emails_after','--resend', metavar="Time string", help="Configure resend_emails_after")
        parser.add_argument('--asynch_workers','--workers', metavar="Number of asynchronous workers", help="Configure asynch_workers", type=int)
        parser.add_argument('--log_file','--log', metavar="Logfile path", help="Configure log_file")
        parser.add_argument('--follow_redirect','--follow',  help="Configure follow_redirect=Yes", action='store_true')
        parser.add_argument('--wpscan_output_folder','--wpout', metavar="WPScan results folder", help="Configure wpscan_output_folder")
        parser.add_argument('--wpscan_args','--wpargs', metavar='WPScan arguments as string', help='Configure wpscan_args')
        parser.add_argument('--false_positive_strings','--fpstr', metavar='False positive strings', help='Configure false_positive_strings', nargs='+', default=None)
        parser.add_argument('--verbose', '-v', help="Configure verbose=Yes", action='store_true')
        parser.add_argument('--quiet', '-q', help="Configure quiet=Yes", action='store_true')
        args = parser.parse_args()
        return(args)

    # Assemble the config dict from args and from file
    @staticmethod
    def build_config_cli(args):
        args=vars(args) if hasattr(args, '__dict__') and not type(args)==dict else args
        # Configuration variables
        conf_files=args['conf'] if 'conf' in args else None
        # Init config dict: read config files
        configuration, files =WPWatcherConfig(files=conf_files).build_config()
        if files: log.info("Load config file(s) : %s"%files)
        conf_args={}
        # Sorting out only args that matches config options and that are not None or False
        for k in args: 
            if k in WPWatcherConfig.DEFAULT_CONFIG.keys() and args[k]:
                conf_args.update({k:args[k]})  

        # Append or init list of urls from file if any
        if 'wp_sites_list' in args and args['wp_sites_list'] :
            with open(args['wp_sites_list'], 'r') as urlsfile:
                sites=[ site.replace('\n','') for site in urlsfile.readlines() ]
                conf_args['wp_sites']= sites if 'wp_sites' not in conf_args else conf_args['wp_sites']+sites

        conf_args=WPWatcherCLI.adjust_special_cli_args(conf_args)
        # Overwrite with conf dict biult from CLI Args
        if conf_args: configuration.update(conf_args)
        return configuration

    @staticmethod
    def adjust_special_cli_args(conf_args):
        # Adjust special case of urls that are list of dict
        if 'wp_sites' in conf_args: conf_args['wp_sites']=[ {"url":site} for site in conf_args['wp_sites'] ]
        # Adjust special case of resend_emails_after
        if 'resend_emails_after' in conf_args: conf_args['resend_emails_after']=parse_timedelta(conf_args['resend_emails_after'])
        # Adjust special case of daemon_loop_sleep
        if 'daemon_loop_sleep' in conf_args: conf_args['daemon_loop_sleep']=parse_timedelta(conf_args['daemon_loop_sleep'])
        # Adjust special case of wpscan_args
        if 'wpscan_args' in conf_args: conf_args['wpscan_args']=shlex.split(conf_args['wpscan_args'])
        return conf_args

def main(): 
    WPWatcherCLI()

if __name__ == '__main__':
    WPWatcherCLI()