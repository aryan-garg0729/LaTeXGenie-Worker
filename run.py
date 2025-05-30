from worker import main
from setup import create_folders
from latexgenie_parser.src.main import run_pipeline
#run from outside folder python latexgenie_parser/run.py
if __name__ == "__main__":
    create_folders()
    main()
    # run_pipeline('D:\LatexGenie-Worker\data\output\input\auto\input_origin.pdf')