# Thesis (Transferarbeit) written in LaTeX

This direcory contains all the source files of the thesis written in LaTeX using TeXlive.

## How to setup TeXLive

This installation instructions are based on using [LaTeX Workshop](https://marketplace.visualstudio.com/items?itemName=James-Yu.latex-workshop) for VSCode and use a docker image to run the actual TeXlive for easy installation.

### Requirements
- A recent version of VSCode
- [LaTeX Workshop Extension](https://marketplace.visualstudio.com/items?itemName=James-Yu.latex-workshop) 
- Docker (Desktop)

### Setup
1. Install the LaTex Workshop extension, if you haven't already
2. Open the `main.tex` file. In the top right across the editor should appear a green `play` button (The same that is used to run scripts/applications)
3. Press the arrow and wait for it to pull the texlive image and create the pdf. While this is ongoing, there is the `Build` indicator active at the left in the bottom status bar of VSCode. 
4. Open the pdf preview (one of the icons next to the `play` button)
5. Change some text and see the changes appear in the pdf after a few seconds. If you have not enables autosave, you need to first save the changes for them to appear