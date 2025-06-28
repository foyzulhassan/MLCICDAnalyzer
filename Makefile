TOOL_NAME = sawra
PY_VERSION = 3.10

install:
	pyinstaller \
		--name "sawra" \
		--clean \
		--onedir \
		./src/__main__.py
	cp -r ./res ./dist/${TOOL_NAME}
	tar -czvf ${TOOL_NAME}.tar.gz -C dist/ ${TOOL_NAME}/
	mv ${TOOL_NAME}.tar.gz ./dist
	rm sawra.spec
	rm -r build
	rm -r dist/sawra