import os
import csv



def get_aws_credentials(rootkey_path='./rootkey.csv'):
    try:
        with open(rootkey_path, 'r') as file:
            csv_reader = csv.reader(file)
            rows = list(csv_reader)

            if len(rows) < 2:
                raise ValueError("CSV file doesn't contain enough rows (needs header and data)")

            headers = rows[0]
            if 'Access key ID' not in headers or 'Secret access key' not in headers:
                access_key_idx = None
                secret_key_idx = None

                for i, header in enumerate(headers):
                    if 'access key id' in header.lower() or 'accesskeyid' in header.lower().replace(" ", ""):
                        access_key_idx = i
                    if 'secret' in header.lower() and 'key' in header.lower():
                        secret_key_idx = i

                if access_key_idx is None or secret_key_idx is None:
                    raise ValueError("Cannot identify the credential columns in the CSV")

                access_key_id = rows[1][access_key_idx].strip()
                secret_access_key = rows[1][secret_key_idx].strip()
            else:
                access_key_idx = headers.index('Access key ID')
                secret_key_idx = headers.index('Secret access key')

                access_key_id = rows[1][access_key_idx].strip()
                secret_access_key = rows[1][secret_key_idx].strip()

            if not access_key_id or not secret_access_key:
                raise ValueError("Found empty credentials in the CSV file")

            os.environ['AWS_ACCESS_KEY_ID'] = access_key_id
            os.environ['AWS_SECRET_ACCESS_KEY'] = secret_access_key

            return (access_key_id, secret_access_key)

    except FileNotFoundError:
        print(f"Error: Could not find file {rootkey_path}")
        return (None, None)
    except Exception as e:
        print(f"Error reading credentials: {e}")
        return (None, None)