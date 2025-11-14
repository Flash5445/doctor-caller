## framework

1. minimalist code is key. do not extrapolate extraneous code to create a better product or attempt to assume the user's "true" intention. follow the prompt by writing the simplest possible code to satisfy the user's query
  
2. never accelerate the development of the project by trying to build out the whole project at once. this project is meant to be modular so stick to the prompt and build out the project one step at a time.
  
3. always use docstrings for functions. make sure to explicitly state the purpose of the function, any arguments required for the function, and the output value of the function
  
4. always make explicit types when you are defining your functions, if possible. this should include both the input types and the output type, if possible.
  
  ```py
  # Good: Proper typing and documentation  
  from typing import List, Optional  
  
  def get_users(limit: int = 10, active_only: bool = True) -> List[User]:  
  """Retrieve users from database with optional filtering.  
  
  Args:  
  limit: Maximum number of users to return  
  active_only: Whether to filter for active users only  
  
  Returns:  
  List of User objects  
  """  
  return db.query(User).filter(User.is_active == active_only).limit(limit).all()  
  
  # Bad: Missing types and documentation
  
  def get_users(limit=10, active=True):  
  return db.query(User).filter(User.is_active == active).limit(limit).all()  
  ```
  
5. create caches for downloaded files to prevent duplicate files and also save time in computation. make sure you explicitly create logic to add/remove files from the cache and comparatives that check whether file downloading is necessary given a cache hit or a cache miss.
  
6. always use pytest to create, edit, and use test files that should be made for each file or feature added. store these test files in /tests and run them upon completion of a file or feature. prefer running single tests and not the whole test suite for performance.
  
7. be sure to use typecheck whenever you are done making a series of code changes.
  
8. destructure import statements whenever possible. use common renaming practices for imports. for example:
  
  ```py
  # goo
  import numpy as np
  import pandas as pd
  from tensorflow import keras
  
  # bad
  import numpy as nmpy
  import pandas as ps
  import tensorflow
  ```
  
9. write modular code. this means that you should be writing code that is able to be scaled in the future to production level applications. while the current scope is just an mvp, this should be scalable to production level output.
  
10. for every new feature implemented, create and iteratively update a docs .md file that you make in /docs. this should be updated and very detailed in order to retain context for future users and LLM code editors to use as context for the specific feature being referenced.
  
11. always use uv as your package manager. use python3 to run files. reference the usage section for more details.
  
12. if specified by user, you must reference the specific .md file that is specified by the user in the /docs/prompts/ folder. thus you will be looking for the file /docs/prompts/[user's query].md. this file will contain the prompt that you are looking for. you must disregard the original user query and only refer to this .md file as your instruction.
  
  a. before answering the prompt for a .md user query, you must say "I understand the prompt."
  
13. always update requirements.txt if you use a new package. then run the following command:
  
  ```bash
  uv pip install -r requirements.txt
  ```
  
14. write all comments and documentation in lowercase unless you are referencing proper nouns.
  

## usage

bash commands (including, but not limited to):

```bash
pytest
uv pip install -r requirements.txt
python3 [insert filename here].py [insert keyword arguments, if needed]
```