{
  description = "The *magical* build system and package manager";

  inputs = {
    nixpkgs.url = "nixpkgs/nixos-23.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        ck = pkgs.python311Packages.buildPythonApplication {
          pyproject = true;
          pname = "cutekit";
          version = "0.7-dev";

          src = ./../..;

          nativeBuildInputs = with pkgs.python311Packages; [ setuptools ];
          propagatedBuildInputs = with pkgs.python311Packages; [
            dataclasses-json
            docker
            requests
            graphviz
          ];
        };
      in
      {
        package.ck = ck;
        defaultPackage = self.package.${system}.ck;
        devShell = pkgs.mkShell {
          buildInputs = [ ck ];
        };
      });
}
