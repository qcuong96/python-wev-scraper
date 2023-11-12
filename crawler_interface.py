import asyncio
import numpy as np
from aiohttp import ClientSession
from multiprocessing import cpu_count
from concurrent.futures import ProcessPoolExecutor, wait


class CrawlerInterface():
    """
    A class used to represent a Crawler Interface.

    ...

    Attributes
    ----------
    num_cores : int
        The number of cores to use for the crawler.
    max_concurrency : int
        The maximum number of concurrent requests.
    parse_html_function : function
        The function to parse the HTML.
    store_function : function, optional
        The function to store the parsed data.
    store_function_kwargs : dict, optional
        The keyword arguments for the store function.
    fetch_function_kwargs : dict, optional
        The keyword arguments for the fetch function.

    Methods
    -------
    fetch(url, session):
        Fetches the HTML from the URL and parses it. If the status code is not 200, it returns an empty dictionary.
    bound_fetch(sem, url, session, *arg, **kwargs):
        Fetches the HTML from the URL with a semaphore.
    asynce_run(urls, *arg, **kwargs):
        Runs the asynchronous tasks for the URLs.
    asyncio_wrapper(urls):
        Wraps the asynchronous run function.
    run(urls):
        Runs the crawler on the URLs. It uses a process pool executor to run the tasks in parallel.
    """

    def __init__(
        self,
        parse_html_function: function,
        store_function: function = None,
        max_concurrency: int = 10,
        num_cores: int = (cpu_count() - 1),
        store_function_kwargs: dict = {},
        fetch_function_kwargs: dict = {},
        **kwargs
    ):
        """
        Constructs all the necessary attributes for the CrawlerInterface object.

        Parameters
        ----------
            parse_html_function : function
                The function to parse the HTML.
            store_function : function, optional
                The function to store the parsed data.
            max_concurrency : int, optional
                The maximum number of concurrent requests.
            num_cores : int, optional
                The number of cores to use for the crawler.
            store_function_kwargs : dict, optional
                The keyword arguments for the store function.
                Ex: db_name, collection_name, etc.
            fetch_function_kwargs : dict, optional
                The keyword arguments for the fetch function.
                Ex: headers, proxies, verify, etc.
        """

        self.num_cores = num_cores
        self.max_concurrency = max_concurrency
        self.parse_html_function = parse_html_function
        self.store_function = store_function
        self.store_function_kwargs = store_function_kwargs
        self.fetch_function_kwargs = fetch_function_kwargs

        for key, value in kwargs.items():
            setattr(self, key, value)

    async def fetch(self, url, session):
        async with session.get(url, **self.fetch_function_kwargs) as response:
            if response.status != 200:
                return {}

            html_body = await response.text()
            data = self.parse_html_function(html_body)

            if self.store_function:
                self.store_function(data, **self.store_function_kwargs)

            return data

    async def bound_fetch(self, sem, url, session, *arg, **kwargs):
        # Getter function with semaphore.
        async with sem:
            return await self.fetch(
                url,
                session,
                *arg,
                **kwargs,
            )

    async def asynce_run(self, urls, *arg, **kwargs):
        tasks = []
        # create instance of Semaphore
        sem = asyncio.Semaphore(self.max_concurrency)

        # Create client session that will ensure we dont open new connection
        # per each request.
        async with ClientSession() as session:
            for url in urls:
                # pass Semaphore and session to every GET request
                task = asyncio.ensure_future(
                    self.bound_fetch(
                        sem,
                        url,
                        session,
                        *arg,
                        **kwargs
                    )
                )

                tasks.append(task)

            responses = await asyncio.gather(*tasks)

            return responses

    def asyncio_wrapper(self, urls):
        return asyncio.run(self.asynce_run(urls))

    def run(self, urls):
        executor = ProcessPoolExecutor(max_workers=self.num_cores)
        tasks = [
            executor.submit(self.asyncio_wrapper, pages_for_task)
            for pages_for_task in np.array_split(urls, self.num_cores)
        ]

        doneTasks, _ = wait(tasks)

        results = [
            task.result()
            for task in doneTasks
        ]

        return sum(results, [])
