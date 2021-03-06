# ==================================================================================================
# Copyright 2013 Twitter, Inc.
# --------------------------------------------------------------------------------------------------
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this work except in compliance with the License.
# You may obtain a copy of the License in the LICENSE file, or at:
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==================================================================================================

"""Support for wholesale archive creation and extraction in a uniform API across archive types."""

import os

from abc import abstractmethod
from zipfile import ZIP_DEFLATED

from twitter.common.collections.ordereddict import OrderedDict
from twitter.common.contextutil import open_tar, open_zip
from twitter.common.lang import AbstractClass


class Archiver(AbstractClass):
  @classmethod
  def extract(cls, path, outdir):
    """Extracts an archive's contents to the specified outdir."""
    raise NotImplementedError()

  @abstractmethod
  def create(self, basedir, outdir, name, prefix=None):
    """Creates an archive of all files found under basedir to a file at outdir of the given name.

    If prefix is specified, it should be prepended to all archive paths.
    """


class TarArchiver(Archiver):
  """An archiver that stores files in a tar file with optional compression."""

  @classmethod
  def extract(cls, path, outdir):
    with open_tar(path) as tar:
      tar.extractall(outdir)

  def __init__(self, mode, extension):
    Archiver.__init__(self)
    self.mode = mode
    self.extension = extension

  def create(self, basedir, outdir, name, prefix=None):
    tarpath = os.path.join(outdir, '%s.%s' % (name, self.extension))
    with open_tar(tarpath, self.mode, dereference=True) as tar:
      tar.add(basedir, arcname=prefix or '')
    return tarpath


class ZipArchiver(Archiver):
  """An archiver that stores files in a zip file with optional compression."""

  @classmethod
  def extract(cls, path, outdir):
    """OS X's python 2.6.1 has a bug in zipfile that makes it unzip directories as regular files.

    This method should work on for python 2.6-3.x.
    """
    with open_zip(path) as zip:
      for path in zip.namelist():
        # While we're at it, we also perform this safety test.
        if path.startswith('/') or path.startswith('..'):
          raise ValueError('Zip file contains unsafe path: %s' % path)
        # Ignore directories. extract() will create parent dirs as needed.
        if not path.endswith('/'):
          zip.extract(path, outdir)

  def __init__(self, compression):
    Archiver.__init__(self)
    self.compression = compression

  def create(self, basedir, outdir, name, prefix=None):
    zippath = os.path.join(outdir, '%s.zip' % name)
    with open_zip(zippath, 'w', compression=ZIP_DEFLATED) as zip:
      for root, _, files in os.walk(basedir):
        for file in files:
          full_path = os.path.join(root, file)
          relpath = os.path.relpath(full_path, basedir)
          if prefix:
            relpath = os.path.join(prefix, relpath)
          zip.write(full_path, relpath)
    return zippath


TAR = TarArchiver('w:', 'tar')
TGZ = TarArchiver('w:gz', 'tar.gz')
TBZ2 = TarArchiver('w:bz2', 'tar.bz2')
ZIP = ZipArchiver(ZIP_DEFLATED)

_ARCHIVER_BY_TYPE = OrderedDict(tar=TGZ, tgz=TGZ, tbz2=TBZ2, zip=ZIP)

TYPE_NAMES = frozenset(_ARCHIVER_BY_TYPE.keys())

def archiver(typename):
  """Returns Archivers in common configurations.

  The typename must correspond to one of the following:
  'tar'   Returns a tar archiver that applies no compression and emits .tar files.
  'tgz'   Returns a tar archiver that applies gzip compression and emits .tar.gz files.
  'tbz2'  Returns a tar archiver that applies bzip2 compression and emits .tar.bz2 files.
  'zip'   Returns a zip archiver that applies standard compression and emits .zip files.
  """
  archiver = _ARCHIVER_BY_TYPE.get(typename)
  if not archiver:
    raise ValueError('No archiver registered for %r' % typename)
  return archiver
