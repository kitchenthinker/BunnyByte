import aiohttp

JOKE_API = "https://v2.jokeapi.dev/joke/Any"


class DadJoke:
    _instance = None  # Keep instance reference

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    @staticmethod
    async def get_joke():
        joke_data = None
        async with aiohttp.ClientSession() as session:
            async with session.get(JOKE_API, cookies={'CONSENT': 'YES+42'}) as r:
                if r.status == 200:
                    joke_data = await r.json()
        if joke_data is None:
            joke = "Nope, there's no any of jokes."
        else:
            joke = joke_data['joke'] if joke_data['type'] == "single" else f"{joke_data['setup']}\n{joke_data['delivery']}"
        return joke
