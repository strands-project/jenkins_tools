#!/usr/bin/env python

import subprocess
import yaml

from catkin_pkg.package import parse_package_string
import rosdistro

print '<html><body>'

i = rosdistro.get_index(rosdistro.get_index_url())
for distro in reversed(sorted(i.distributions.keys())):
    d = rosdistro.get_cached_distribution(i, distro)
    f = d._distribution_file
    print '<h1>%s</h1>' % distro
    print '<table>'
    for repo_name in sorted(f.repositories.keys()):
        repo = f.repositories[repo_name]
        if not repo.release_repository:
            continue
        if not repo.doc_repository and not repo.source_repository:
            continue

        release_repo = repo.release_repository
        if release_repo.version is None:
            continue
        url = release_repo.url

        strands_prefix = 'https://github.com/strands-project-releases'
        if not url.startswith(strands_prefix):
            continue

        prefix = 'https://github.com/'
        if not url.startswith(prefix):
            raise RuntimeError('wrong prefix')
        suffix = '.git'
        if not url.endswith(suffix):
            raise RuntimeError('wrong suffix')

        tracks_url = 'https://raw.githubusercontent.com/' + url[len(prefix):]
        tracks_url = tracks_url[:-len(suffix)] + '/master/tracks.yaml'
        #print(repo_name, tracks_url)

        tracks_yaml = rosdistro.loader.load_url(tracks_url)
        #print(tracks_yaml)

        try:
            tracks_data = yaml.load(tracks_yaml)
            upstream_url = tracks_data['tracks'][distro]['vcs_uri']
            # ignore local upstream path
            if upstream_url.startswith('/'):
                continue
        except:
            continue

        last_version=tracks_data['tracks'][distro]['last_version']
        release_tag=tracks_data['tracks'][distro]['release_tag'].replace(':{version}', last_version)

        remotes = subprocess.check_output(['git', 'ls-remote', upstream_url])
        lines = remotes.splitlines()
        lines = [l.split('\t') for l in lines]
        head_hash = [l[0] for l in lines if l[1] == 'HEAD'][0]
        default_ref = [l[1] for l in lines if l[0] == head_hash and l[1] != 'HEAD'][0]
        release_branch = tracks_data['tracks'][distro]['devel_branch']
        if release_branch is None:
            release_branch = default_ref.split('/')[-1]

        #print release_branch, repo_name, tracks_data['tracks'][distro]
        tag_hash = [l[0] for l in lines if l[1] == 'refs/tags/'+release_tag][0]
        release_branch_hash = [l[0] for l in lines if l[1] == 'refs/heads/'+release_branch][0]

        if not tag_hash == release_branch_hash:
            style = "color:red"
        else:
            style = "color:green"
        print '<tr style=%s><td>%s</td> <td>%s <i>(%s)</i></td> <td>%s <i>(%s)</i></td></tr>' % (style, repo_name, last_version, tag_hash , release_branch, release_branch_hash)

#        if repo.source_repository:
#            source_branch = repo.source_repository.version
#            if source_branch != release_branch:
#                print(repo_name, 'source', source_branch, 'vs.', 'rel', release_branch)
    print '</table>'
print '</body></html>'
