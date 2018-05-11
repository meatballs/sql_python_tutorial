import pathlib
import tqdm
import collections
import jinja2

from nbconvert import HTMLExporter

ROOT = 'sql_python_tutorial'


def get_id(path):
    """
    Return the id of a file
    """
    stem = path.stem
    try:
        return stem[:stem.index('-')]
    except ValueError:
        stem = stem.lower()
        stem = stem.replace(" ", "-")
        stem = stem.replace(",", "")
        return stem


def get_name(path):
    """
    Return the name of a file
    """
    stem = path.stem
    try:
        return stem[stem.index('-'):].replace('-', ' ')
    except ValueError:
        return stem


def convert_html(nb_path):
    """
    Convert a notebook to html
    """
    html_exporter = HTMLExporter()
    html_exporter.template_file = "basic"
    return html_exporter.from_file(str(nb_path))


def render_template(template_file, template_vars):
    """
    Render a jinja2 template
    """
    templateLoader = jinja2.FileSystemLoader(searchpath="./templates/")
    template_env = jinja2.Environment(loader=templateLoader)
    template = template_env.get_template(template_file)
    return template.render(template_vars)


def make_dir(path, directory, previous_url=None, next_url=None):
    """
    Create a directory for the name of the file
    """
    path_id = get_id(path)
    p = pathlib.Path(f"./{directory}/{path_id}")
    p.mkdir(exist_ok=True)
    nb, _ = convert_html(path)
    nb = nb.replace("{{root}}", ROOT)
    html = render_template("notebook.html", {"nb": nb,
        "root": ROOT,
        "id": path_id,
        "previous_url": previous_url,
        "next_url": next_url})
    (p / 'index.html').write_text(html)


def make_collection(paths, directory,
                    make_previous_url=True,
                    make_next_url=True):

    number_of_paths = len(paths)
    for index, filename in enumerate(paths):
        previous_path = paths[(index - 1) % number_of_paths]
        previous_id = get_id(previous_path)

        next_path = paths[(index + 1) % number_of_paths]
        next_id = get_id(next_path)

        make_dir(pathlib.Path(filename), directory=directory,
                 previous_url=previous_id,
                 next_url=next_id)


Chapter = collections.namedtuple("chapter", ["dir", "title", "nb"])


if __name__ == "__main__":

    nb_dir = pathlib.Path('notebooks')
    chapter_paths = sorted(nb_dir.glob('./*ipynb'))

    for paths, directory in [(chapter_paths, "chapters")]:
        make_collection(paths=paths, directory=directory)

    chapters = []
    for path in tqdm.tqdm(sorted(chapter_paths)):
        chapters.append(Chapter(f"{get_id(path)}",
                                get_name(path), str(path)))

    pages = [
      {'template': 'home.html', 'output': 'index.html'},
      {'template': 'intro.html', 'output': 'pages/intro.html'},
      {'template': 'howto.html', 'output': 'pages/howto.html'},
      {'template': 'primer.html', 'output': 'pages/primer.html'}]
    for page in pages:
      html = render_template(f'pages/{page["template"]}', {'root': ROOT})
      with open(page['output'], 'w') as f:
          f.write(html)

    html = render_template(
      "chapters.html", {"chapters": chapters, "root": ROOT})
    with open('./chapters/index.html', 'w') as f:
        f.write(html)
