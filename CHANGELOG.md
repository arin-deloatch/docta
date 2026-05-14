# Changelog

## [0.2.4](https://github.com/arin-deloatch/docta/compare/v0.2.3...v0.2.4) (2026-05-14)


### Bug Fixes

* adjusting boolean test assertion to reflect new changes ([d1930de](https://github.com/arin-deloatch/docta/commit/d1930decae115cbeceee9a53be54b1ef06799fc9))
* **docker:** install qa extra in poller image to resolve langchain_core import ([4faedb4](https://github.com/arin-deloatch/docta/commit/4faedb42cce75fa07c715c0d6cabb894ac9b3da7))
* **models:** default run_qa_generation to False for safer bare configs ([f48337d](https://github.com/arin-deloatch/docta/commit/f48337d0b94cc58bb102ff5a64f65a082c83a831))

## [0.2.3](https://github.com/arin-deloatch/docta/compare/v0.2.2...v0.2.3) (2026-05-13)


### Bug Fixes

* **docker:** make Dockerfile and k8s manifest OpenShift-compatible ([ec34d5e](https://github.com/arin-deloatch/docta/commit/ec34d5e94b589b58453a7d60583a6faf4e41f02e))


### Documentation

* **docker:** update README with pre-built image usage and fix stale commands ([5890b2e](https://github.com/arin-deloatch/docta/commit/5890b2e8b732a6a764ee89b97d8b54d4ef86e3e3))

## [0.2.2](https://github.com/arin-deloatch/docta/compare/v0.2.1...v0.2.2) (2026-05-11)


### Documentation

* add mkdocs.yml with Material theme configuration ([b98c94d](https://github.com/arin-deloatch/docta/commit/b98c94d59ad8935e361a280414e89e86712b5421))
* add text hint to fenced code blocks for ASCII diagrams ([ab8d85c](https://github.com/arin-deloatch/docta/commit/ab8d85c8ad8b976ed5323c571091039ccaa65990))
* migrate README into docs/ directory for GitHub Pages ([4926e3f](https://github.com/arin-deloatch/docta/commit/4926e3f1fe41144bcff54f899b66f9029ea17ab8))
* slim README to landing page pointing to GitHub Pages site ([f4b74f3](https://github.com/arin-deloatch/docta/commit/f4b74f38469787802e57f1a3a19444d51e59ff33))

## [0.2.1](https://github.com/arin-deloatch/docta/compare/v0.2.0...v0.2.1) (2026-05-11)


### Bug Fixes

* **security:** address CodeRabbit review findings ([ad2edce](https://github.com/arin-deloatch/docta/commit/ad2edce221f6ec842f80aa0135fcb82fb5f78440))
* **security:** extend FORBIDDEN_SYSTEM_DIRS with OS-protected binary and library paths ([25a3634](https://github.com/arin-deloatch/docta/commit/25a36349e684ad2ad4e0e0fcecc652a8c28aa2e0))
* **security:** replace hardcoded tmp/graphql_polling with tempfile.TemporaryDirectory ([2c4d13f](https://github.com/arin-deloatch/docta/commit/2c4d13f0803b3c09ad15d848001ca87db8285dfc))
* **security:** resolve SSL cert path truthiness bug and wire ContentConfig.verify_ssl ([bf61670](https://github.com/arin-deloatch/docta/commit/bf6167030f4fb5a10ed637bad763da13fb576291))
* **security:** sanitize HTTPError messages before writing to stderr and logs ([d58b860](https://github.com/arin-deloatch/docta/commit/d58b860beadda1b1735ea2e8df91e3ea1baa67a5))


### Documentation

* **security:** document fcntl Linux-only and NFS limitations in state.py ([cd93d84](https://github.com/arin-deloatch/docta/commit/cd93d84bc4094345b6c3d7cb15afbe34da56a77b))

## [0.2.0](https://github.com/arin-deloatch/docta/compare/v0.1.2...v0.2.0) (2026-05-08)


### Features

* **qa:** add GenerationSummary model and supporting types ([9b4b3f3](https://github.com/arin-deloatch/docta/commit/9b4b3f3ccc4622974921420c370620d7592af3ee))
* **qa:** add write_generation_summary to qa_writer ([8b741f0](https://github.com/arin-deloatch/docta/commit/8b741f02edb48add23218b110aa6908bfec548fd))
* **qa:** wire GenerationSummary into orchestrator pipeline ([c984ecd](https://github.com/arin-deloatch/docta/commit/c984ecd5aab56016d748a45bdec14eecd0baea88))


### Documentation

* update AGENTS.md to reflect full toolchain accurately ([9407298](https://github.com/arin-deloatch/docta/commit/94072988153fdc931cf0da24aa2a615e32e9919a))

## [0.1.2](https://github.com/arin-deloatch/docta/compare/v0.1.1...v0.1.2) (2026-05-07)


### Documentation

* remove redundant h1 title from README ([04fca03](https://github.com/arin-deloatch/docta/commit/04fca034cacaa1949284f8deb4fdea7efe04c5aa))

## [0.1.1](https://github.com/arin-deloatch/docta/compare/v0.1.0...v0.1.1) (2026-05-07)


### Bug Fixes

* set build context to repo root in build-push workflow ([#21](https://github.com/arin-deloatch/docta/issues/21)) ([505a705](https://github.com/arin-deloatch/docta/commit/505a705c9c99fcb449737f14a37f49975984a0ac))

## 0.1.0 (2026-05-06)


### Features

* add AddedDocumentStats and document_added change type ([db057b2](https://github.com/arin-deloatch/docta/commit/db057b27749e8a778e2451e8ee5d11e571a41072))
* add bug report issue template ([6bad971](https://github.com/arin-deloatch/docta/commit/6bad971501e4b0391b57881e95ea5c104c0db09b))
* add CLI commands for added document QA generation ([3878626](https://github.com/arin-deloatch/docta/commit/387862664dced445556882d3e25a39e5bff1cbaa))
* add CLI for QA generation ([4a7a46d](https://github.com/arin-deloatch/docta/commit/4a7a46da7bc2b16a0c9adbb386264baf17c18c3a))
* add CLI for QA generation ([4b8367d](https://github.com/arin-deloatch/docta/commit/4b8367d7f32c96badce239ccac5992dafe651eef))
* add configuration settings system ([7c496e9](https://github.com/arin-deloatch/docta/commit/7c496e925bb51290f619d4fcd0d43baf0bd8e491))
* add daemon CLI commands for GraphQL polling service ([0f728c3](https://github.com/arin-deloatch/docta/commit/0f728c3c5b6cbc28a45e67c09aa185055ddd901b))
* add directories for certificates and fetched content ([52aa5cc](https://github.com/arin-deloatch/docta/commit/52aa5ccc9b683e1596fae1d82c0e253b9056f7b3))
* add Docker deployment configuration for polling daemon ([3940fba](https://github.com/arin-deloatch/docta/commit/3940fbad4fdc6fe7a89694a24a13c3b349cd39b2))
* add feature request issue template ([42a304c](https://github.com/arin-deloatch/docta/commit/42a304c2e271899a2bf117dad2f35f8cd2681758))
* add framework-agnostic LLMManager and EmbeddingManager ([5bada37](https://github.com/arin-deloatch/docta/commit/5bada37b1a961b9ba495f6a6567a7661edbd9206))
* add generator protocol and exceptions ([2be327d](https://github.com/arin-deloatch/docta/commit/2be327d259e40c11a14bbd5d7574df5f8417000a))
* add GraphQL client and content fetcher ([b3dcbbf](https://github.com/arin-deloatch/docta/commit/b3dcbbfd19ae3bc77d7221ed7ed3ea3a6917aad3))
* add GraphQL polling configuration ([46baeb6](https://github.com/arin-deloatch/docta/commit/46baeb631aaf72df65487abf31198b0816cf499e))
* add GraphQL polling configuration loader ([07674bf](https://github.com/arin-deloatch/docta/commit/07674bfd5e5ce98bbae44f98a37b01d256088a76))
* add GraphQL polling service data models ([b58e532](https://github.com/arin-deloatch/docta/commit/b58e5323fe2174b61aede01a7530a391a41f4280))
* add ingest modules for added document processing ([9527f0f](https://github.com/arin-deloatch/docta/commit/9527f0ff18b73bff52d4098a71457a8029a9f144))
* add LLM provider factory ([dfdd757](https://github.com/arin-deloatch/docta/commit/dfdd7572aeccc4ffa83b9b2a298935bb5daaa77d))
* add metadata field to SourceDocumentInfo ([67ff6cb](https://github.com/arin-deloatch/docta/commit/67ff6cb516d88e769c285312b1bff2dce829140c))
* add pipeline functions for delta report processing ([97a8fe1](https://github.com/arin-deloatch/docta/commit/97a8fe1b906a7a12b51e3ba191e7baf42a15f61d))
* add pipeline runner for automated diff and QA generation ([cb16582](https://github.com/arin-deloatch/docta/commit/cb1658292d3b5c6760d56c18cbd445130f02b425))
* add pipeline status tracking and document workspace management ([bf3b810](https://github.com/arin-deloatch/docta/commit/bf3b810f5e740cc8a927cdf12cfc8a26eb733a77))
* add placeholder Kubernetes manifests for docta poller ([d24ad7c](https://github.com/arin-deloatch/docta/commit/d24ad7cb72c8f669dbe00d77fa3b176ec10c9771))
* add polling scheduler for GraphQL document monitoring ([c09970e](https://github.com/arin-deloatch/docta/commit/c09970e7d70ecfed900a0819a2fb6c50cd8a9a3a))
* add pull request template ([c0e6959](https://github.com/arin-deloatch/docta/commit/c0e6959ef3b10c790fcf354f3bbc6183f4f91308))
* add pydantic-settings and requests dependencies ([19c19dc](https://github.com/arin-deloatch/docta/commit/19c19dc68334763346a6a8d3387141d15d288185))
* add QA generation pipeline orchestrator ([8c49e82](https://github.com/arin-deloatch/docta/commit/8c49e825dad4a5826dd92b0e5ac54cca05786282))
* add QA generation pipeline orchestrator ([7283fb3](https://github.com/arin-deloatch/docta/commit/7283fb305c3cbdbc6570b1d0b759e165a8fad659))
* add RAGAS adapters and testset generator factory ([33434c3](https://github.com/arin-deloatch/docta/commit/33434c3c866ac9afad82f12b99424a40a3a3e47f))
* add RAGAS QA generator implementation ([e000d24](https://github.com/arin-deloatch/docta/commit/e000d2445656ff47bcc1cf4a70412ad878c88ecd))
* add robust error handling to RAGAS generator ([a211b6b](https://github.com/arin-deloatch/docta/commit/a211b6b9f6101116c4692ef85e338293a262f81e))
* add state persistence manager with version tracking ([18ac33f](https://github.com/arin-deloatch/docta/commit/18ac33faf3d4b76b9a0e81c32b5b9e3280183b06))
* add stratified topic sampling for QA generation ([1f8b86c](https://github.com/arin-deloatch/docta/commit/1f8b86c1106ae446a175402e8dffa6ba998f3c46))
* add timestamps and flow metadata through RAGAS pipeline ([c42ca66](https://github.com/arin-deloatch/docta/commit/c42ca66e689360641cf79458a2cbdf73d60e08a7))
* added example env vars + deps updates ([e0ce772](https://github.com/arin-deloatch/docta/commit/e0ce772308217361f5d8bc3d71bad03fce5abbfc))
* added ingestion module + some pydantic and constant fixes ([c14042b](https://github.com/arin-deloatch/docta/commit/c14042bb27bafbfc987e5df7dc4b744de1e53caa))
* added support for writing plain text to semantic diff report + replaced magic #s with constants ([c1865ae](https://github.com/arin-deloatch/docta/commit/c1865aea7141a4c4be79a887293adbf3419d5dae))
* adding baseline system config file for qa generation ([d4bdf17](https://github.com/arin-deloatch/docta/commit/d4bdf1706da987870a380a6ffe0b8817487af1f3))
* adding synthetic qa generation using RAGAS ([709af8b](https://github.com/arin-deloatch/docta/commit/709af8b2f0930c16fdc4a2db876a569ad3865060))
* data modeling for qa pairs + report ingestion ([c8e33cc](https://github.com/arin-deloatch/docta/commit/c8e33cc31688711886697463372f3f49f1b69df7))
* doc comparison,extraction and data modeling logic ([595b7e3](https://github.com/arin-deloatch/docta/commit/595b7e329cae709754cbe44b031b6cd5f4e67876))
* document comparison logic with cli integration ([68e1e6b](https://github.com/arin-deloatch/docta/commit/68e1e6b9562835ec1fd1fbef1bea2921c68337f1))
* json reporting + utility functions, constant declaration, etc. ([0176f13](https://github.com/arin-deloatch/docta/commit/0176f13104f6038bbdc12b37e06140b348894a07))
* **qa:** add num_documents config option to generation settings ([4ea4ff8](https://github.com/arin-deloatch/docta/commit/4ea4ff8c1a25028a59932406a62487640706399a))
* **qa:** integrate num_documents config in CLI commands ([2d5e5f4](https://github.com/arin-deloatch/docta/commit/2d5e5f4f1f885f7aeaee91eccd43cebbb42747d8))
* replaced logger with structlog ([a97a1cb](https://github.com/arin-deloatch/docta/commit/a97a1cb05d71d9f4537ac69cbae6ddf6ca8f98a9))
* store document_content for added documents ([c1225a2](https://github.com/arin-deloatch/docta/commit/c1225a226dfa508eba8dd052409f9a89f3b33da4))
* store old/new content in QASourceDocument for modified docs ([794a44e](https://github.com/arin-deloatch/docta/commit/794a44e6673c629a79cbe03f79241c0fec4c0ffb))


### Bug Fixes

* add explicit UTF-8 encoding to file operations ([dbf2b55](https://github.com/arin-deloatch/docta/commit/dbf2b554b3cbf3b18eeb1d6aa8e16b03378e237f))
* add missing make targets and pytest configuration ([5529d59](https://github.com/arin-deloatch/docta/commit/5529d59fad6b14e4e2dd641f0de4eda2952db10f))
* added artifacts directory to .ignore file + updated README to reflect current state ([7425890](https://github.com/arin-deloatch/docta/commit/742589068ffcc8ab676a8281d1ed943da7a1abb1))
* address CodeRabbit review feedback ([1b0f39e](https://github.com/arin-deloatch/docta/commit/1b0f39e146c3f7139c1ea6aaebecec303a7432bd))
* addressing coderabbit nitpick comments ([9f189f4](https://github.com/arin-deloatch/docta/commit/9f189f460a529dfc0c462e19e82406eb86d5e2b5))
* **ci:** update format check command in PR workflow ([274288f](https://github.com/arin-deloatch/docta/commit/274288fbb9650dad701715ed3e5722e42d849794))
* closes [#16](https://github.com/arin-deloatch/docta/issues/16); requests pin ([#17](https://github.com/arin-deloatch/docta/issues/17)) ([4289059](https://github.com/arin-deloatch/docta/commit/4289059b52c0f17dec11367aa6e05dea70a349bf))
* coderabbit fix ([bac64bb](https://github.com/arin-deloatch/docta/commit/bac64bbc349fa88a8d993f71263922c8cd6977de))
* configuration updates ([dec9db0](https://github.com/arin-deloatch/docta/commit/dec9db009c4d1e5b210f5240f7d6657610f4f4bf))
* correct inaccuracies in README for public release ([c30b1b3](https://github.com/arin-deloatch/docta/commit/c30b1b34b61f53d660fced651afc0f6946b86b97))
* **daemon:** pass num_documents from settings to QA generation ([e7c72ef](https://github.com/arin-deloatch/docta/commit/e7c72ef64262bb3a3188bd9a23edb5f709225ea4))
* double file extension ([bb3b751](https://github.com/arin-deloatch/docta/commit/bb3b7515e001983365f447515a439c11bd49a0e6))
* env comments ([ba000e7](https://github.com/arin-deloatch/docta/commit/ba000e75f0bd01f60f439e1be5429934952e3516))
* fail stratified generation if no QA pairs generated ([dec5917](https://github.com/arin-deloatch/docta/commit/dec59175afa4337b912b458afc0e6b8f12428dda))
* **fetcher:** use actual byte count in oversize error and add constants ([feb0b14](https://github.com/arin-deloatch/docta/commit/feb0b14589f78fc769cdec799e688311dcf743e6))
* **graphql:** add runtime validation for OAuth and GraphQL responses ([9aa15ba](https://github.com/arin-deloatch/docta/commit/9aa15ba741074d1820e8161c91bb38c346d309c0))
* improve GraphQL client scope handling and model flexibility ([faebe30](https://github.com/arin-deloatch/docta/commit/faebe3072005562e7e50cdfcd80d7d6ad45484c1))
* model validator + ambiguous naming convention ([31789d6](https://github.com/arin-deloatch/docta/commit/31789d62aeaf841f7f4535c0bdc47d4557d81f62))
* model validator + ambiguous naming convention ([e686193](https://github.com/arin-deloatch/docta/commit/e6861937916498244aeaa2cfca1d7095a56767df))
* **mypy:** configure handling for optional QA dependencies ([08a6ca6](https://github.com/arin-deloatch/docta/commit/08a6ca66d71be7f6b71703153ba81ab2b74c7f2c))
* pyright missingimports ([336e428](https://github.com/arin-deloatch/docta/commit/336e428f99de0b203e4c4ba259838b2d1d7a356d))
* **qa:** add document_added to valid change types ([563edc7](https://github.com/arin-deloatch/docta/commit/563edc7d9240f2932da1c43d228294e6e34e30dd))
* **qa:** add JSON root type validation in report loading ([4545614](https://github.com/arin-deloatch/docta/commit/4545614c10ee0127c0dd6448487618d3cc7185ec))
* remediations per coderabbits suggestions ([6facebe](https://github.com/arin-deloatch/docta/commit/6facebe671f528e54412ece4cd3600982f9e1ef6))
* removed diffed plain text truncation and incorrect html being displayed ([c2633ea](https://github.com/arin-deloatch/docta/commit/c2633ea8c40bbd882344114971d463630a6d1128))
* return extraction stats from snippet extractor ([703a8c5](https://github.com/arin-deloatch/docta/commit/703a8c59e1a64ba50a6c3e758f9e269b7000d8c4))
* return extraction stats from snippet extractor ([be25f6e](https://github.com/arin-deloatch/docta/commit/be25f6e69228e46548293a145f6d53f9c08a451f))
* ruff formatting ([c1c7f0d](https://github.com/arin-deloatch/docta/commit/c1c7f0d7b5a80f5210bd20fae01cf1a0056db333))
* updated deps for qa + qa_generation package init ([11543f2](https://github.com/arin-deloatch/docta/commit/11543f2d68beda35d5f9380088983cd1852c15cc))
* updates per CodeRabbit ([2f6e7fe](https://github.com/arin-deloatch/docta/commit/2f6e7feb67ab43a97865be8caf4ace2044be4375))
* updates to cli ([3841157](https://github.com/arin-deloatch/docta/commit/38411571005d160841135188e11f7aea6483752d))
* use directory form for .claude/ in gitignore ([7228feb](https://github.com/arin-deloatch/docta/commit/7228feb6e29082f5c2cae7179d3d5bef92890776))


### Performance Improvements

* **qa:** apply num_documents limit during extraction, not after ([535a8f8](https://github.com/arin-deloatch/docta/commit/535a8f89e98c58e3f21170ca8cca80fc42d37010))


### Documentation

* add header comment to eval data template ([bdd80ed](https://github.com/arin-deloatch/docta/commit/bdd80ed697bea89767dbf728d504bf5e50fe7da3))
* restructure README and sanitize examples ([1e3fa9d](https://github.com/arin-deloatch/docta/commit/1e3fa9daa38c4e2085185627c8444d78365cdb04))
* update example files with GraphQL config and generic placeholders ([60d3809](https://github.com/arin-deloatch/docta/commit/60d3809d61577c3c24b44262e262fec6b6c87faa))
* update README to reference docta.png asset ([cab53fd](https://github.com/arin-deloatch/docta/commit/cab53fddbea0735d3ce6cc1ee75aae69c595f1f0))
* update README.md for docta rename ([d53008c](https://github.com/arin-deloatch/docta/commit/d53008c2c79974ea460afca93829256420e4262b))
