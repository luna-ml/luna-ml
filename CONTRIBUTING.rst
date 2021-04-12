Contributing
====================
We welcome community contributions to the project. This page provides useful information for contribution.

.. contents:: **Table of Contents**
  :local:
  :depth: 4

Contribution process
####################
Code contribution process starts with filing a GitHub issue. Community members of the project will review the code
and decide to merge. Once your pull request against the repository has been merged, your corresponding changes
will be automatically included in the next release.

Congratulations, you have just contributed to the project. We appreciate your contribution!

Contribution guidelines
#######################
In this section, we provide guidelines to consider as you develop new features and patches.

Write designs for significant changes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For significant changes, we recommend outlining a design for the feature or patch and discussing it with
community members before investing heavily in implementation. During issue triage, we try to proactively
identify issues require design. This is particularly important if your proposed implementation:

- Introduces changes or additions to the REST API

  - The REST API is implemented by a variety of open source and proprietary platforms. Changes to the REST
    API impact all of these platforms. Accordingly, we encourage developers to thoroughly explore alternatives
    before attempting to introduce REST API changes.

- Introduces new user-facing APIs

  - API surface is carefully designed to generalize across a variety of common operations.
    It is important to ensure that new APIs are broadly useful to developers, easy to work with,
    and simple yet powerful.

- Adds new library dependencies

- Makes changes to critical internal abstractions.

Make changes backwards compatible
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Users rely on specific platform and API behaviors in their daily workflows. As new versions
are developed and released, it is important to ensure that users' workflows continue to
operate as expected. Accordingly, please take care to consider backwards compatibility when introducing
changes to the code base. If you are unsure of the backwards compatibility implications of
a particular change, feel free to ask community member for input.


Sign your work
#############################

Configure Git
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
First, ensure that your name and email are
`configured in git <https://git-scm.com/book/en/v2/Getting-Started-First-Time-Git-Setup>`_ so that
you can `sign your work`_ when committing code changes and opening pull requests:

.. code-block:: bash

    git config --global user.name "Your Name"
    git config --global user.email yourname@example.com

For convenience, we provide a pre-commit git hook that validates that commits are signed-off.
Enable it by running:

.. code-block:: bash

    git config core.hooksPath hooks


Commit
~~~~~~~~~~~~~~

In order to commit your work, you need to sign that you wrote the patch or otherwise have the right 
to pass it on as an open-source patch. If you can certify the below (from developercertificate.org)::

  Developer Certificate of Origin
  Version 1.1

  Copyright (C) 2004, 2006 The Linux Foundation and its contributors.
  1 Letterman Drive
  Suite D4700
  San Francisco, CA, 94129

  Everyone is permitted to copy and distribute verbatim copies of this
  license document, but changing it is not allowed.


  Developer's Certificate of Origin 1.1

  By making a contribution to this project, I certify that:

  (a) The contribution was created in whole or in part by me and I
      have the right to submit it under the open source license
      indicated in the file; or

  (b) The contribution is based upon previous work that, to the best
      of my knowledge, is covered under an appropriate open source
      license and I have the right under that license to submit that
      work with modifications, whether created in whole or in part
      by me, under the same open source license (unless I am
      permitted to submit under a different license), as indicated
      in the file; or

  (c) The contribution was provided directly to me by some other
      person who certified (a), (b) or (c) and I have not modified
      it.

  (d) I understand and agree that this project and the contribution
      are public and that a record of the contribution (including all
      personal information I submit with it, including my sign-off) is
      maintained indefinitely and may be redistributed consistent with
      this project or the open source license(s) involved.


Then add a line to every git commit message::

  Signed-off-by: Jane Smith <jane.smith@email.com>

Use your real name (sorry, no pseudonyms or anonymous contributions). You can sign your commit 
automatically with ``git commit -s`` after you set your ``user.name`` and ``user.email`` git configs.

