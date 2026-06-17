from settings import settings


def main():
    print(settings.DATABASE_URL)
    print(settings.model_dump_json(indent=4))


if __name__ == "__main__":
    main()
