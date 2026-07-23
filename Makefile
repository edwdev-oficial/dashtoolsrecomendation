run:
	poetry run streamlit run app.py

test:
	poetry run python -m unittest discover -s tests -v	