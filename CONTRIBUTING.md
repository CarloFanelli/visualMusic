# Contributing

Thanks for your interest in visualMusic. Issues and pull requests are welcome.

## Before you start

- Open an issue to discuss larger changes before writing code.
- Follow the setup in the [README](README.md), and run the tests before opening a pull request:

  ```shell
  .venv/bin/python -m pytest
  ```

## Rules for images and videos

- Never commit images, videos, model weights or anything in `data/`: `.gitignore` blocks them, and pull requests containing them will not be merged.
- New image sources must offer only CC0, public domain or CC BY images, and record title, author, license and source link for each image in the manifest.
- Add frames only from videos you own or have the rights to use, and never add images of people who have not agreed to it.

## Licensing of contributions

By submitting a contribution you confirm that you wrote it or have the right to submit it, and you agree that it is licensed under the same terms as the project, the [GNU Affero General Public License v3.0](LICENSE).

## Removal requests

If you are the author of an image used to train a published model and want it removed, open an issue with its link: it will be excluded from future trainings.
