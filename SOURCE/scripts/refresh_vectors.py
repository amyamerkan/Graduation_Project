import argparse
import json

from vn_assistant.vector_refresh import refresh_vectors


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()
    print(json.dumps(refresh_vectors(args.dataset, args.seed, args.output, device=args.device,
                                     batch_size=args.batch_size), ensure_ascii=False, indent=2))
