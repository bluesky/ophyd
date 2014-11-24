DEST_PATH:=../../ophyd/utils
HTML_SOURCE:=html

all: install

install: ad_docs.py
	cp ad_docs.py ${DEST_PATH}/

ad_docs.py: gen.py $(HTML_SOURCE)/*.html
	if [ ! -d $(HTML_SOURCE) ]; then \
		echo "* HTML source not found (try 'make download')"; \
		exit 1; \
	fi

	python gen.py $(HTML_SOURCE) > ad_docs.py

download:
	wget --cut-dirs=3 --directory-prefix=$(HTML_SOURCE) -nH -r -N -l 1 --no-remove-listing http://cars9.uchicago.edu/software/epics/areaDetectorDoc.html
