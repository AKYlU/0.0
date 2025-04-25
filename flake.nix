{
  description = "newm - Wayland compositor";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";  # base do sistema
    flake-utils.url = "github:numtide/flake-utils";        # utilitários p/ multiplataforma

    pywmpkg.url = "github:jbuchermn/pywm";                 # dependência externa
    pywmpkg.inputs.nixpkgs.follows = "nixpkgs";            # usa mesmo nixpkgs
  };

  outputs = { self, nixpkgs, pywmpkg, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          overlays = [
            (self: super: rec {
              # Override do python3 com pacotes extras
              python3 = super.python3.override {
                packageOverrides = self1: super1: {
                  pywm = pywmpkg.packages.${system}.pywm;

                  dasbus = super1.buildPythonPackage rec {
                    pname = "dasbus";
                    version = "1.6";
                    src = super1.fetchPypi {
                      inherit pname version;
                      sha256 = "sha256-FJrY/Iw9KYMhq1AVm1R6soNImaieR+IcbULyyS5W6U0=";
                    };
                    doCheck = true;
                    propagatedBuildInputs = with super1; [ pygobject3 ];
                  };

                  thefuzz = super1.buildPythonPackage rec {
                    pname = "thefuzz";
                    version = "0.19.0";
                    src = super1.fetchPypi {
                      inherit pname version;
                      sha256 = "sha256-b3Em2y8silQhKwXjp0DkX0KRxJfXXSB1Fyj2Nbt0qj0=";
                    };
                    propagatedBuildInputs = with super1; [
                      python-Levenshtein
                      pycodestyle
                    ];
                  };
                };
              };

              python3Packages = python3.pkgs;  # alias p/ pacotes
            })
          ];
        };
      in
      {
        # Pacote exposto como "newm"
        packages.newm = pkgs.python3Packages.buildPythonApplication rec {
          pname = "newm";
          version = "0.3alpha";
          src = ./.;
          doCheck = true;

          propagatedBuildInputs = with pkgs.python3Packages; [
            pywm
            pycairo
            psutil
            python-pam
            pyfiglet
            dasbus
            thefuzz
            setuptools
          ];
        };

        # Shell de desenvolvimento com LSP e utilitários
        devShell = let
          my-python = pkgs.python3;
          python-with-my-packages = my-python.withPackages (ps: with ps; [
            pywm
            pycairo
            psutil
            python-pam
            pyfiglet
            dasbus
            thefuzz
            python-lsp-server
            (pylsp-mypy.overrideAttrs (old: { pytestCheckPhase = "true"; }))
            mypy
            yappi
          ]);
        in pkgs.mkShell {
          buildInputs = [ python-with-my-packages ];
        };
      }
    );
}
