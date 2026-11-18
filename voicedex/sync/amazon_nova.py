"""
Amazon Nova Sonic — speech-to-speech foundation models on Amazon Bedrock.

Source: docs. Models, lifecycle dates and regions come from the Bedrock model cards and model-lifecycle
pages; voices and locales from the Nova user guide; prices from the Bedrock pricing page (the AWS Price
List API carries the same per-token rates). Bedrock's ListFoundationModels API needs AWS credentials
we don't use for sync — docs-only until an AWS account is wired in. Amazon Polly and Amazon Transcribe
are separate providers.
"""

from voicedex.sync.docs_only import DocsOnlySyncer


class AmazonNovaSyncer(DocsOnlySyncer):
    provider_id = "amazon-nova"
    sts_docs = [
        "https://docs.aws.amazon.com/bedrock/latest/userguide/model-cards.html",
        "https://docs.aws.amazon.com/bedrock/latest/userguide/model-lifecycle-legacy.html",
        "https://docs.aws.amazon.com/nova/latest/nova2-userguide/using-conversational-speech.html",
        "https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-language-support.html",
        "https://aws.amazon.com/bedrock/pricing/",
    ]
    voices_docs = [
        "https://docs.aws.amazon.com/nova/latest/nova2-userguide/sonic-language-support.html",
    ]
    sts_guidance = (
        "Return every Nova Sonic speech-to-speech model callable on Amazon Bedrock by its exact Bedrock model "
        "ID, from its model card. Skip models past their EOL date; models in Legacy state get eol_date = the "
        "published EOL date. Regions: map the documented AWS regions to us/eu/asia (never guess global). "
        "Pricing per token as published (base = speech input; variants for speech output, text input, text "
        "output). Exactly one is_default: the newest Active model."
    )
    voices_guidance = (
        "Return every documented Nova Sonic voice id (lowercase, as used in voiceId) with gender, locale(s) "
        "and accent. A voice id listed under several locales is one voice with all of them; voices documented "
        "as speaking all supported languages get multilingual_native. compatible_models: only the model ids "
        "the page documents the voices for."
    )
