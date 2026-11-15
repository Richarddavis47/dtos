[Skip to contents](https://nflverse.nflverse.com/#main)

![](https://nflverse.nflverse.com/logo.png)

# nflverse  [anchor](https://nflverse.nflverse.com/\#nflverse-)

## Overview [anchor](https://nflverse.nflverse.com/\#overview)

The nflverse is a set of packages dedicated to data of the National Football League. The **nflverse** package is designed to make it easy to install and load core packages from the nflverse in a single command. Please see the [nflverse organisation repo](https://github.com/nflverse/nflverse-org) on more information about governance, the code of conduct and possible roles.

## Installation [anchor](https://nflverse.nflverse.com/\#installation)

The easiest way to get nflverse is to install it from [CRAN](https://cran.r-project.org/package=nflverse) with:

```
install.packages("nflverse")
```

To get a bug fix or to use a feature from the development version, you can install the development version of nflverse either from [GitHub](https://github.com/nflverse/nflverse/) with:

```
if (!require("pak")) install.packages("pak")
pak::pak("nflverse/nflverse")
```

or prebuilt from the [development repo](https://nflverse.r-universe.dev/) with:

```
install.packages("nflverse", repos = c("https://nflverse.r-universe.dev", getOption("repos")))
```

## Usage [anchor](https://nflverse.nflverse.com/\#usage)

`library(nflverse)` will load the following nflverse packages:

- [nflfastR](https://www.nflfastr.com/), for play-by-play data back to 1999.
- [nflseedR](https://nflseedr.com/), for season simulations.
- [nfl4th](https://www.nfl4th.com/), for 4th down analysis.
- [nflreadr](https://nflreadr.nflverse.com/), for fast end efficient nflverse data downloads.
- [nflplotR](https://nflplotr.nflverse.com/), for tools to create visualization of NFL related analysis.

## Getting help [anchor](https://nflverse.nflverse.com/\#getting-help)

The best places to get help on this package are:

- the [nflverse discord](https://discord.com/invite/5Er2FBnnQa) (for both this package as well as anything R/NFL related)
- opening [an issue](https://github.com/nflverse/nflverse/issues/new/choose)

## Contributing [anchor](https://nflverse.nflverse.com/\#contributing)

Many hands make light work! Here are some ways you can contribute to this project:

- You can [open an issue](https://github.com/nflverse/nflverse/issues/new/choose) if you’d like to request specific data or report a bug/error.

- If you’d like to contribute code, please check out [the contribution guidelines](https://nflverse.nflverse.com/CONTRIBUTING.html).


## Terms of Use [anchor](https://nflverse.nflverse.com/\#terms-of-use)

The R code for this package is released as open source under the [MIT License](https://nflverse.nflverse.com/LICENSE.html). NFL data accessed by this package belong to their respective owners, and are governed by their terms of use.
