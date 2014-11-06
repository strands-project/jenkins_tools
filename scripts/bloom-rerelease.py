#!/usr/bin/env python

import jenkins
import argparse
import os
import sys
import termios
import tty
import yaml
from tempfile import mkdtemp
from rosdistro import get_index, get_index_url, get_distribution_file


import subprocess
from subprocess import Popen, CalledProcessError


def parse_options():
    import argparse
    parser = argparse.ArgumentParser(
        description='re-release to an existing STRANDS bloom repo.'
    )
    parser.add_argument(
        'repo_name',
        help='A read-only git buildpackage repo uri.',
    )
    parser.add_argument('rosdistro', help='Which rosdistro to operate on')
    parser.add_argument('track', help='Which track to release to')
    parser.add_argument('--bump',
                        help='Version number to bump. Default: %(default)s',
                        default='patch')

    args = parser.parse_args()

    return args

class Releaser:

    def __init__(self, repo, distro_name, track, bump):
        self.repo_name = repo
        self.track = track
        self.distro_name = distro_name
        self.bump = bump

        try:
            index = get_index(get_index_url())
            self.distribution = get_distribution_file(
                index,
                self.distro_name
            )
            self.repo = self.distribution.repositories[self.repo_name]
        except:
            print "failed to get data about repo %s in distribution %s" % (self.repo_name, self.distro_name)
            raise

    def call(self, working_dir, command, pipe=None):
        print('+ cd %s && ' % working_dir + ' '.join(command))
        process = Popen(command, stdout=pipe, stderr=pipe, cwd=working_dir)
        output, unused_err = process.communicate()
        retcode = process.poll()
        if retcode:
            raise CalledProcessError(retcode, command)
        if pipe:
            return output

    def bloom_release(self):
        empty_dir = mkdtemp()
        self.call(empty_dir,
            [
                'bloom-release',
                '-t', self.track, '-r', self.distro_name, '--noweb',  '-y', '-s'
            ])

    def prepare_upstream(self):
        upstream_dir = mkdtemp()
        upstream_url = self.repo.source_repository.url
        try:
            self.call(upstream_dir, ['git', 'clone', upstream_url, upstream_dir])
            self.call(upstream_dir, ['catkin_generate_changelog', '-y'])
            self.call(upstream_dir, ['git', 'commit' ,'-a', '-m', 'updated changelogs'])
            self.call(upstream_dir, ['catkin_prepare_release', '-y', '--bump', self.bump])
            self.call('/', ['rm', '-rf', upstream_dir])
        except:
            print 'error in preparing upstream at %s' % upstream_dir
            raise



if __name__ == "__main__":
    args = parse_options()
    r = Releaser(args.repo_name, args.rosdistro, args.track, args.bump)

    r.prepare_upstream()

