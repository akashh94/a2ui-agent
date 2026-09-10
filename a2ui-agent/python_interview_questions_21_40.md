# Python Interview Questions (21 - 40)

### 21. Explain List Comprehension in Python.
List comprehension provides a concise way to create lists. It consists of brackets containing an expression followed by a `for` clause, then zero or more `for` or `if` clauses. It is generally faster and more readable than using traditional loops.
**Syntax:** `[expression for item in iterable if condition]`
**Example:** Creating a list of squares for even numbers.
```python
squares = [x**2 for x in range(10) if x % 2 == 0]
# Output: [0, 4, 16, 36, 64]
```

### 22. Explain Dictionary Comprehension.
Similar to list comprehensions, dictionary comprehensions allow you to construct dictionaries concisely.
**Syntax:** `{key_expression: value_expression for item in iterable if condition}`
**Example:**
```python
square_dict = {x: x**2 for x in range(5)}
# Output: {0: 0, 1: 1, 2: 4, 3: 9, 4: 16}
```

### 23. What are Generators in Python?
Generators are a simple way to create iterators using functions. Instead of returning a single value, a generator uses the `yield` keyword to return a sequence of values one at a time, pausing execution and saving its state between calls. This makes them highly memory-efficient for large datasets (lazy evaluation).
```python
def my_generator():
    yield 1
    yield 2
```

### 24. How is Concurrency achieved in Python?
Concurrency in Python can be achieved in three main ways:
1.  **Threading (`threading` module):** Good for I/O-bound tasks. Multiple threads share the same memory space.
2.  **Multiprocessing (`multiprocessing` module):** Bypasses the GIL by spawning multiple OS processes. Good for CPU-bound tasks.
3.  **Asynchronous I/O (`asyncio` module):** Uses an event loop and coroutines for cooperative multitasking, highly efficient for network-bound tasks.

### 25. Coroutines vs. Threads
*   **Threads:** Managed by the OS (preemptive multitasking). They run concurrently, but in CPython, the GIL prevents multiple threads from executing Python bytecode simultaneously. Context switching has overhead.
*   **Coroutines:** Managed by the application/event loop (cooperative multitasking) using `async`/`await`. They run sequentially on a single thread and explicitly yield control. They use much less memory and have lower context-switching overhead than threads.

### 26. What is the GIL (Global Interpreter Lock)?
The GIL is a mutex (lock) in CPython that protects access to Python objects, preventing multiple native threads from executing Python bytecodes at once. It makes memory management thread-safe but prevents true parallel execution of Python code in multi-threaded programs. (Note: True parallelism for CPU-bound tasks requires `multiprocessing`).

### 27. How do you optimize Python performance?
*   Use built-in functions and libraries (they are often implemented in C).
*   Use appropriate data structures (e.g., sets for lookups instead of lists).
*   Profile the code using `cProfile` to find bottlenecks.
*   Use List Comprehensions and Generators.
*   Use `multiprocessing` for CPU-bound tasks.
*   Use C extensions (Cython) or alternative interpreters like PyPy.

### 28. What is a Context Manager and the `with` statement?
A context manager is an object that defines the runtime context to be established when executing a `with` statement. It ensures proper acquisition and release of resources (like closing files or releasing locks), even if exceptions occur. It implements `__enter__()` and `__exit__()` methods.
```python
with open('file.txt', 'r') as f:
    content = f.read()
# f is automatically closed here
```

### 29. How do you optimize memory in Python?
*   Use **Generators** instead of lists for large datasets.
*   Use `__slots__` in classes to prevent the creation of `__dict__` for each instance, saving memory.
*   Use `del` to remove unused large variables.
*   Use efficient libraries like NumPy for large numerical data arrays.

### 30. What is Monkey Patching?
Monkey patching refers to dynamically modifying a class or module at runtime. While it can be useful for quickly fixing a bug or mocking behaviors during testing, it is generally discouraged in production code because it can make the code difficult to understand and debug.
```python
import math
math.pi = 3.14 # Monkey patching the math module
```

### 31. What are Classes in Python?
Classes are blueprints for creating objects. They define a set of attributes (variables) and methods (functions) that characterize any object instantiated from the class.

### 32. Does Python fully support Object-Oriented Programming (OOP)?
Yes, Python is a multi-paradigm language that fully supports OOP. Everything in Python is an object. It supports the core principles of OOP: Encapsulation, Inheritance, and Polymorphism.

### 33. Explain Inheritance in Python.
Inheritance allows one class (child/subclass) to inherit attributes and methods from another class (parent/base class). It promotes code reusability. Python supports both single and multiple inheritance.

### 34. What is Encapsulation and how is it implemented?
Encapsulation is the bundling of data and the methods that operate on that data into a single unit (class), while restricting direct access to some of the object's components. Python doesn't have strict access modifiers like `private`, but relies on conventions:
*   `_variable`: Protected (should not be accessed directly outside the class).
*   `__variable`: Private (invokes name mangling to prevent accidental access).

### 35. Class Methods vs. Static Methods vs. Instance Methods
*   **Instance Methods:** Take `self` as the first parameter. They access and modify instance state.
*   **Class Methods:** Created using `@classmethod`. Take `cls` as the first parameter. They modify class state that applies across all instances.
*   **Static Methods:** Created using `@staticmethod`. They take neither `self` nor `cls`. They operate like regular functions but belong to the class's namespace.

### 36. What is Polymorphism in Python?
Polymorphism means "many forms." In Python, it allows objects of different classes to be treated as if they were objects of a common superclass. This is primarily achieved through method overriding and "duck typing" (if it walks like a duck and quacks like a duck, it's a duck).

### 37. What is the `super()` function?
`super()` returns a proxy object that allows you to refer to the parent class. It is most commonly used in the `__init__` method of a child class to ensure the parent class is properly initialized, and it elegantly handles complex Multiple Inheritance structures by following the MRO.

### 38. What is MRO (Method Resolution Order)?
MRO dictates the order in which Python searches for base classes when executing a method. It uses the C3 linearization algorithm. In cases of multiple inheritance, it ensures that a class always precedes its parents, and multiple parents are checked in the order they are listed. You can view it using `ClassName.__mro__`.

### 39. What are Magic Methods (Dunder Methods)?
Magic methods are special methods surrounded by double underscores (e.g., `__init__`, `__str__`, `__add__`). They allow you to define how your custom objects behave with built-in Python operations like addition (+), string representation, or initialization. They are the mechanism behind operator overloading.

### 40. Can you prevent inheritance in Python?
Python does not have a built-in `final` keyword like Java to strictly prevent inheritance. Python's philosophy is "we are all consenting adults here," meaning developers should respect documentation over strict enforcement. However, if absolutely necessary, you can prevent inheritance by using a custom Metaclass that raises a `TypeError` if a class attempts to inherit from the target class.