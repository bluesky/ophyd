DEST_PATH:=../../ophyd/controls/areadetector
HTML_SOURCE:=html
FILENAME=docs.py

all: install

install: $(FILENAME)
	cp $(FILENAME) ${DEST_PATH}/

$(FILENAME): gen.py $(HTML_SOURCE)/*.html
	if [ ! -d $(HTML_SOURCE) ]; then \
		echo "* HTML source not found (try 'make download')"; \
		exit 1; \
	fi

	python gen.py $(HTML_SOURCE) > $(FILENAME)

download:
	wget --cut-dirs=3 --directory-prefix=$(HTML_SOURCE) -nH -r -N -l 1 --no-remove-listing http://cars9.uchicago.edu/software/epics/areaDetectorDoc.html
