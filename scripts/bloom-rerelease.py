#!/usr/bin/env python

import argparse
import os
import sys
import termios
import tty
import yaml
from tempfile import mkdtemp
from rosdistro import get_index, get_index_url, get_distribution_file
import subprocess

from catkin_pkg.package import parse_package_string
import rosdistro


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
    parser.add_argument('--track', help='Also run bloom after preparing upstream with this track', default=None)
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
        self.pretend = False

        try:
            self.index = get_index(get_index_url())
            self.distribution = get_distribution_file(
                self.index,
                self.distro_name
            )
            self.repo = self.distribution.repositories[self.repo_name]
        except:
            print "failed to get data about repo %s in distribution %s" % (self.repo_name, self.distro_name)
            raise

    def get_release_upstream_repo(self):
        repo = self.repo
        distro = self.distro_name
        if not repo.release_repository:
            raise  RuntimeError('no release repo exists')

        release_repo = repo.release_repository
        if release_repo.version is None:
            raise  RuntimeError('no release version exists')

        url = release_repo.url

        prefix = 'https://github.com/'
        if not url.startswith(prefix):
            raise RuntimeError('wrong prefix')
        suffix = '.git'
        if not url.endswith(suffix):
            raise RuntimeError('wrong suffix')

        tracks_url = 'https://raw.githubusercontent.com/' + url[len(prefix):]
        tracks_url = tracks_url[:-len(suffix)] + '/master/tracks.yaml'
        

        tracks_yaml = rosdistro.loader.load_url(tracks_url)
        

        tracks_data = yaml.load(tracks_yaml)
        upstream_url = tracks_data['tracks'][distro]['vcs_uri']
        # ignore local upstream path

        last_version=tracks_data['tracks'][distro]['last_version']
        release_tag=tracks_data['tracks'][distro]['release_tag'].replace(':{version}', last_version)


        release_branch = tracks_data['tracks'][distro]['devel_branch']
        if release_branch is None:
            remotes = subprocess.check_output(['git', 'ls-remote', upstream_url])
            lines = remotes.splitlines()
            lines = [l.split('\t') for l in lines]
            head_hash = [l[0] for l in lines if l[1] == 'HEAD'][0]
            default_ref = [l[1] for l in lines if l[0] == head_hash and l[1] != 'HEAD'][0]
            release_branch = default_ref.split('/')[-1]

        self.upstream_url = upstream_url
        self.release_branch = release_branch
        return upstream_url, release_branch
        #print release_branch, repo_name, tracks_data['tracks'][distro]
        #tag_hash = [l[0] for l in lines if l[1] == 'refs/tags/'+release_tag][0]
        #release_branch_hash = [l[0] for l in lines if l[1] == 'refs/heads/'+release_branch][0]



    def call(self, working_dir, command, pipe=None):
        print('+ cd %s && ' % working_dir + ' '.join(command))
        if not self.pretend:
            process = Popen(command, stdout=pipe, stderr=pipe, cwd=working_dir)
            output, unused_err = process.communicate()
            retcode = process.poll()
            if retcode:
                raise CalledProcessError(retcode, command)
            if pipe:
                return output
        else:
            return ''

    def bloom_release(self):
        self.call('/',
            [
                'bloom-release',
                '-t', self.track, '-r', self.distro_name, '--noweb',  '-y', '-s'
            ])

    def prepare_upstream(self):
        upstream_dir = mkdtemp()
        upstream_url = self.upstream_url
        try:
            self.call(upstream_dir, ['git', 'clone', '-b', self.release_branch, upstream_url, upstream_dir])

            try:
                self.call(upstream_dir, ['catkin_generate_changelog', '-y',  '-a'])
            except:
                pass
            self.call(upstream_dir, ['catkin_generate_changelog', '-y'])

            for root, dirs, files in os.walk(upstream_dir):
                if 'CHANGELOG.rst' in files:
                    cl_path = '%s/CHANGELOG.rst' % root
                    self.call(upstream_dir, ['git', 'add', cl_path])
            self.call(upstream_dir, ['git', 'commit' ,'-a', '-m', 'updated changelogs'])


            self.call(upstream_dir, ['catkin_prepare_release', '-y', '--bump', self.bump])
            self.call('/', ['rm', '-rf', upstream_dir])
        except:
            print 'error in preparing upstream at %s' % upstream_dir
            raise



if __name__ == "__main__":
    args = parse_options()
    r = Releaser(args.repo_name, args.rosdistro, args.track, args.bump)

    r.get_release_upstream_repo()
    

    r.prepare_upstream()
    if args.track is not None:
        r.bloom_release()
