import logging


def setup_logger():
    logging.basicConfig(
        level=logging.DEBUG,  # 로그 레벨 설정
        format="%(asctime)s:%(levelname)s:%(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p",
        handlers=[logging.StreamHandler()],  # 콘솔 출력 핸들러 추가
    )
