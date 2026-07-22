# Vendored from Flask-CacheBust: https://github.com/ChrisTM/Flask-CacheBust
#
# The MIT License (MIT)
#
# Copyright (c) 2015 Christopher Mitchell, CloudBolt Software
#
# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"),
# to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import hashlib
import os


def setup_cache_busting(app):
    """
    Configure `app` to so that `url_for` adds a unique prefix to URLs generated
    for the `'static'` endpoint. Also make the app able to serve cache-busted
    static files.
    This allows setting long cache expiration values on static resources
    because whenever the resource changes, so does its URL.
    """
    # the rooted path to the static file folder
    static_folder = app.static_folder
    # map from an unbusted filename to a busted one
    bust_table = {}
    # map from a busted filename to an unbusted one
    unbust_table = {}

    app.logger.debug('Computing cache-busting values...')
    # compute (un)bust tables.
    for dirpath, _dirnames, filenames in os.walk(static_folder):
        for filename in filenames:
            # compute version component
            rooted_filename = os.path.join(dirpath, filename)
            with open(rooted_filename, 'rb') as f:
                version = 'c' + hashlib.md5(f.read()).hexdigest()[:7]

            # add version
            unbusted = os.path.relpath(rooted_filename, static_folder)
            busted = os.path.join(version, unbusted)

            # save computation to tables
            bust_table[unbusted] = busted
            unbust_table[busted] = unbusted
    app.logger.debug('Finished computing cache-busting values')

    def bust_filename(filename):
        return bust_table.get(filename, filename)

    def unbust_filename(filename):
        return unbust_table.get(filename, filename)

    @app.url_defaults
    def reverse_to_cache_busted_url(endpoint, values):
        """
        Make `url_for` produce busted filenames when using the 'static'
        endpoint.
        """
        if endpoint == 'static':
            values['filename'] = bust_filename(values['filename'])

    def debusting_static_view(filename):
        """
        Serve a request for a static file having a busted name.
        """
        return original_static_view(filename=unbust_filename(filename))

    # Replace the default static file view with our debusting view.
    original_static_view = app.view_functions['static']
    app.view_functions['static'] = debusting_static_view
