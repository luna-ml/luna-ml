class ScoreFile():

    @staticmethod
    def fromText(text: str):
        score = {}
        for line in text.split("\n"):
            line = line.strip()
            if line == "":
                continue

            m = re.match("([^ ]+)\s+([^ ]+).*", line)
            if m == None:
                continue

            try:
                key = m.group(1)
                value = float(m.group(2))
            except ValueError:
                continue

            score[key] = value

        return score