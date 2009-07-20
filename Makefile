NAME=colorname

TARBALL=$(wildcard dist/colorname-*.tar.gz)

USER=foosel
HOST=ni.recluse.de
TARGET=/srv/www/vhosts/org/foosel/code/html/files
SCP=scp

all: release

.dist:
	rm -r dist
	./setup.py sdist

release: .dist
	$(SCP) $(TARBALL) $(USER)@$(HOST):$(TARGET)
	python2.5 setup.py sdist upload --sign
