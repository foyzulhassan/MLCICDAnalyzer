TOOL_NAME = sawra
PY_VERSION = 3.10

install:
	pyinstaller \
		--onedir \
		--clean \
		--name ${TOOL_NAME} \
		--distpath "./dist" \
		--workpath "./dist/build" \
		--paths "./.venv/lib/python${PY_VERSION}/site-packages" \
		./src/__main__.py
	cp -r ./res ./dist/${TOOL_NAME}
	tar -czvf ${TOOL_NAME}.tar.gz -C dist/ ${TOOL_NAME}/
	mv ${TOOL_NAME}.tar.gz ./dist